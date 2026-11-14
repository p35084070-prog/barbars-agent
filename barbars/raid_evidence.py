"""Read-only dragon evidence. Never infer a party loss from one dead hero.

Only server combat rows and icon values are retained: no URLs, forms, chat,
cookies or complete HTML. Percent HP is deliberately separate from absolute HP.
"""
from html.parser import HTMLParser
import re

from .driver import normalize_ru


class _Node:
    def __init__(self, tag="", attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children = []

    def text(self):
        if self.tag in {"script", "style", "form", "footer"}:
            return ""
        if "chat" in (self.attrs.get("id", "") + self.attrs.get("class", "")).lower():
            return ""
        return " ".join(c if isinstance(c, str) else c.text() for c in self.children)


class _Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.node = _Node()
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = _Node(tag, attrs, self.node)
        self.node.children.append(n)
        self.nodes.append(n)
        if tag not in {"img", "br", "hr", "input", "meta", "link", "area", "source", "wbr"}:
            self.node = n

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.node.tag == tag:
            self.node = self.node.parent

    def handle_endtag(self, tag):
        n = self.node
        while n.parent:
            if n.tag == tag:
                self.node = n.parent
                return
            n = n.parent

    def handle_data(self, text):
        self.node.children.append(text)


def _flat(text):
    return " ".join(text.split())


def parse_dragon_evidence(html):
    tree = _Tree(html)
    result = {"boss_hp_pct": None, "warriors_alive": None, "medics_alive": None,
              "combat_clock": None, "events": [], "terminal": None,
              "terminal_evidence": [], "personal_dead": False, "notices": []}
    icons = {"dragon_mif": "boss_hp_pct", "blue_warrior": "warriors_alive",
             "blue_healer": "medics_alive", "clock": "combat_clock"}
    # Read the adjacent span of the known dragon icon, not any percent on page.
    for n in tree.nodes:
        if n.tag != "img":
            continue
        icon = n.attrs.get("src", "").split("/")[-1].split(".")[0]
        if icon in icons:
            siblings = n.parent.children
            for sibling in siblings[siblings.index(n) + 1:]:
                if isinstance(sibling, str):
                    if sibling.strip():
                        break
                    continue
                if sibling.tag != "span":
                    break
                value = _flat(sibling.text())
                if icon == "clock" and re.fullmatch(r"\d+:\d{2}(?::\d{2})?", value):
                    result[icons[icon]] = value
                elif icon == "dragon_mif" and re.fullmatch(r"(?:100|\d{1,2})(?:[.,]\d+)?%", value):
                    result[icons[icon]] = float(value[:-1].replace(",", "."))
                elif icon != "dragon_mif" and value.isdigit():
                    result[icons[icon]] = int(value)
                break
        # Combat log rows have a direct clock2 icon in captured real pages.
        if icon == "clock2":
            row = _flat(n.parent.text())
            if row and len(row) <= 500:
                result["events"].append(row)
    # Explicit outcome labels outside chat/forms; avoid whole-page substring
    # matches ('Лучшие', navigation and clan-chat messages are not a win).
    for n in tree.nodes:
        if n.tag not in {"div", "span", "h1", "h2", "p"}:
            continue
        if any(isinstance(c, _Node) and c.tag in {"div", "form", "p"} for c in n.children):
            continue
        ancestor = n
        excluded = False
        while ancestor.parent:
            if ancestor.tag in {"a", "form", "script", "style", "footer"} or "chat" in (ancestor.attrs.get("id", "") + ancestor.attrs.get("class", "")).lower():
                excluded = True
                break
            ancestor = ancestor.parent
        if excluded:
            continue
        text = _flat(n.text())
        low = normalize_ru(text)
        if (0 < len(text) <= 300 and re.search(r"дракон|побед|поражен|погиб|убит|вылеч|исцел|бой|урон|леч", low)
                and not any(isinstance(c, _Node) and c.tag in {"a", "input", "button"} for c in n.children)):
            if text not in result["notices"]:
                result["notices"].append(text)
        if re.search(r"\bты (?:погиб|м[её]ртв|убит)\b", low):
            result["personal_dead"] = True
        win = bool(re.fullmatch(r"(?:победа[!.]?|(?:мифический )?дракон (?:повержен|побежд[её]н|убит)[!.]?|(?:ваш |твой )?отряд победил(?: дракона)?[!.]?)", low))
        loss = bool(re.fullmatch(r"(?:(?:ваш |твой )?отряд (?:погиб|уничтожен|проиграл)[!.]?|все (?:герои|участники|союзники) погибли[!.]?)", low))
        if re.fullmatch(r"поражение[!.]?", low):
            # A personal loss panel can coexist with surviving allies.
            loss = result["warriors_alive"] == 0 and result["medics_alive"] == 0
        if win or loss:
            result["terminal_evidence"].append(text[:250])
            value = "победа" if win else "поражение"
            if result["terminal"] and result["terminal"] != value:
                result["terminal"] = "противоречивые данные"
            else:
                result["terminal"] = value
    if (result["terminal"] is None and result["personal_dead"]
            and result["warriors_alive"] == 0 and result["medics_alive"] == 0
            and result["boss_hp_pct"] is not None and result["boss_hp_pct"] > 0
            and result["combat_clock"] is not None):
        result["terminal"] = "поражение"
        result["terminal_evidence"].append("боевой экран: герой погиб, живых воинов 0, медиков 0, HP дракона > 0%")
    return result


def record_sample(active, evidence, now):
    """Keep progress and a conservative lower bound from overlapping log rows."""
    previous = active.get("combat_log_window", [])
    current = evidence.get("events", [])
    overlap = 0
    newest_first = False
    for size in range(min(len(previous), len(current)), 0, -1):
        if previous[-size:] == current[:size]:
            overlap = size
            break
        if previous[:size] == current[-size:]:
            overlap = size
            newest_first = True
            break
    if previous and current == previous:
        new = []  # identical repeated hits cannot safely be distinguished
        active["event_totals_exact"] = False
    else:
        new = current[:-overlap] if newest_first and overlap else current[overlap:]
        if previous and not overlap:
            active["event_totals_exact"] = False
    active["combat_log_window"] = current
    for row in new:
        low = normalize_ru(row)
        m = re.search(r"ты\s+ударил\s+дракона\s+на\s+(\d[\d\s]*)", low)
        if m:
            active["damage_lower_bound"] = active.get("damage_lower_bound", 0) + int(re.sub(r"\D", "", m[1]))
        m = re.search(r"ты\s+(?:вылечил|исцелил)\b.*?\bна\s+(\d[\d\s]*)", low)
        if m:
            active["healing_lower_bound"] = active.get("healing_lower_bound", 0) + int(re.sub(r"\D", "", m[1]))
        if len(active.setdefault("recent_events", [])) < 100:
            active["recent_events"].append(row)
    sample = {k: evidence.get(k) for k in ("boss_hp_pct", "warriors_alive", "medics_alive", "combat_clock", "our_hp", "our_energy", "terminal", "personal_dead", "terminal_evidence", "notices")}
    sample["at"] = now
    if evidence.get("personal_dead") or evidence.get("our_hp") == 0:
        active["personal_death_confirmed"] = True
    pct = evidence.get("boss_hp_pct")
    if pct is not None:
        active.setdefault("boss_initial_hp_pct", pct)
        active["boss_last_hp_pct"] = pct
        active["boss_min_hp_pct"] = min(pct, active.get("boss_min_hp_pct", pct))
    active["latest_evidence"] = sample
    return sample
