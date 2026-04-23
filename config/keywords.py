from dataclasses import dataclass, field
from typing import List


@dataclass
class CategorySpec:
    category: str
    subcategory: str
    queries: List[str]
    is_smart: bool = False
    min_price_usd: float = 0.0
    family: str = ""


CATEGORIES: List[CategorySpec] = [
    CategorySpec("traditional", "guitar",
                ["acoustic guitar", "classical guitar", "travel guitar", "dreadnought guitar"],
                min_price_usd=60, family="plucked_string"),
    CategorySpec("traditional", "electric_guitar",
                ["electric guitar", "stratocaster guitar", "les paul guitar", "telecaster guitar"],
                min_price_usd=80, family="plucked_string"),
    CategorySpec("traditional", "bass_guitar",
                ["bass guitar", "4 string bass", "5 string bass"],
                min_price_usd=100, family="plucked_string"),
    CategorySpec("traditional", "ukulele",
                ["ukulele", "soprano ukulele", "concert ukulele", "tenor ukulele"],
                min_price_usd=25, family="plucked_string"),
    CategorySpec("traditional", "harp",
                ["lever harp", "lyre harp", "celtic harp", "pedal harp"],
                min_price_usd=60, family="plucked_string"),
    CategorySpec("traditional", "mandolin",
                ["mandolin", "f-style mandolin", "a-style mandolin"],
                min_price_usd=60, family="plucked_string"),
    CategorySpec("traditional", "banjo",
                ["banjo", "5-string banjo", "bluegrass banjo"],
                min_price_usd=80, family="plucked_string"),

    CategorySpec("traditional", "violin",
                ["violin", "student violin", "4/4 violin", "electric violin"],
                min_price_usd=40, family="bowed_string"),
    CategorySpec("traditional", "cello",
                ["cello", "student cello", "4/4 cello", "full size cello"],
                min_price_usd=200, family="bowed_string"),
    CategorySpec("traditional", "viola",
                ["viola instrument", "student viola", "16 inch viola"],
                min_price_usd=80, family="bowed_string"),
    CategorySpec("traditional", "double_bass",
                ["upright bass instrument", "double bass instrument", "contrabass"],
                min_price_usd=300, family="bowed_string"),

    CategorySpec("traditional", "acoustic_piano",
                ["upright piano", "grand piano", "spinet piano"],
                min_price_usd=500, family="struck_string"),
    CategorySpec("traditional", "digital_piano",
                ["digital piano", "88 key digital piano", "weighted key piano", "stage piano"],
                min_price_usd=150, family="struck_string"),
    CategorySpec("traditional", "hammered_dulcimer",
                ["hammered dulcimer", "mountain dulcimer"],
                min_price_usd=100, family="struck_string"),

    CategorySpec("traditional", "flute",
                ["concert flute", "student flute", "silver flute", "piccolo flute"],
                min_price_usd=40, family="woodwind_edge"),
    CategorySpec("traditional", "clarinet",
                ["clarinet instrument", "Bb clarinet", "student clarinet", "bass clarinet"],
                min_price_usd=50, family="woodwind_reed"),
    CategorySpec("traditional", "oboe",
                ["oboe instrument", "student oboe", "english horn"],
                min_price_usd=100, family="woodwind_reed"),
    CategorySpec("traditional", "saxophone",
                ["alto saxophone", "tenor saxophone", "soprano saxophone", "student saxophone"],
                min_price_usd=150, family="woodwind_reed"),

    CategorySpec("traditional", "trumpet",
                ["trumpet instrument", "Bb trumpet", "student trumpet", "pocket trumpet"],
                min_price_usd=80, family="brass"),
    CategorySpec("traditional", "trombone",
                ["trombone instrument", "tenor trombone", "student trombone"],
                min_price_usd=150, family="brass"),
    CategorySpec("traditional", "french_horn",
                ["french horn", "single french horn", "double french horn"],
                min_price_usd=200, family="brass"),

    CategorySpec("traditional", "marimba",
                ["marimba instrument", "concert marimba", "student marimba"],
                min_price_usd=80, family="idiophone"),
    CategorySpec("traditional", "xylophone",
                ["xylophone instrument", "student xylophone", "glockenspiel"],
                min_price_usd=25, family="idiophone"),
    CategorySpec("traditional", "gong",
                ["chau gong", "bao gong", "wind gong"],
                min_price_usd=30, family="idiophone"),
    CategorySpec("traditional", "cymbals",
                ["drum cymbals", "crash cymbal", "ride cymbal", "hi hat cymbal"],
                min_price_usd=50, family="idiophone"),

    CategorySpec("traditional", "acoustic_drum",
                ["acoustic drum kit", "5 piece drum set", "jazz drum kit", "snare drum"],
                min_price_usd=150, family="membranophone"),
    CategorySpec("traditional", "djembe",
                ["djembe drum", "african djembe", "wooden djembe"],
                min_price_usd=40, family="membranophone"),
    CategorySpec("traditional", "cajon",
                ["cajon drum", "cajon percussion", "flamenco cajon"],
                min_price_usd=50, family="membranophone"),
    CategorySpec("traditional", "timpani",
                ["timpani drum", "kettle drum"],
                min_price_usd=200, family="membranophone"),

    CategorySpec("traditional", "guzheng",
                ["guzheng", "chinese zither", "21 string guzheng"],
                min_price_usd=150, family="chinese_plucked"),
    CategorySpec("traditional", "guqin",
                ["guqin", "chinese 7 string zither", "chinese qin"],
                min_price_usd=150, family="chinese_plucked"),
    CategorySpec("traditional", "pipa",
                ["pipa instrument", "chinese lute pipa", "4 string pipa"],
                min_price_usd=120, family="chinese_plucked"),
    CategorySpec("traditional", "erhu",
                ["erhu", "chinese violin", "2 string erhu"],
                min_price_usd=40, family="chinese_bowed"),
    CategorySpec("traditional", "dizi",
                ["dizi bamboo flute", "chinese bamboo flute", "dizi flute"],
                min_price_usd=15, family="chinese_wind"),
    CategorySpec("traditional", "hulusi",
                ["hulusi", "cucurbit flute", "chinese hulusi"],
                min_price_usd=15, family="chinese_wind"),
    CategorySpec("traditional", "suona",
                ["suona", "chinese trumpet suona", "suona horn"],
                min_price_usd=25, family="chinese_wind"),
    CategorySpec("traditional", "yangqin",
                ["yangqin", "chinese dulcimer", "yang qin"],
                min_price_usd=150, family="chinese_struck"),
    CategorySpec("traditional", "morin_khuur",
                ["morin khuur", "horsehead fiddle", "mongolian fiddle"],
                min_price_usd=80, family="world"),

    CategorySpec("traditional", "sitar",
                ["sitar instrument", "indian sitar", "student sitar"],
                min_price_usd=100, family="world"),
    CategorySpec("traditional", "tabla",
                ["tabla drum", "indian tabla", "tabla set"],
                min_price_usd=80, family="world"),
    CategorySpec("traditional", "shamisen",
                ["shamisen", "japanese shamisen", "tsugaru shamisen"],
                min_price_usd=100, family="world"),
    CategorySpec("traditional", "oud",
                ["oud instrument", "arabic oud", "turkish oud"],
                min_price_usd=100, family="world"),
    CategorySpec("traditional", "didgeridoo",
                ["didgeridoo", "aboriginal didgeridoo", "bamboo didgeridoo"],
                min_price_usd=40, family="world"),

    CategorySpec("modern", "synthesizer",
                ["synthesizer keyboard", "analog synthesizer", "modular synthesizer", "virtual analog synth"],
                min_price_usd=100, family="electronic"),
    CategorySpec("modern", "electronic_drum",
                ["electronic drum kit", "electronic drum set", "mesh head drum kit"],
                is_smart=True, min_price_usd=150, family="electronic"),
    CategorySpec("modern", "electronic_keyboard",
                ["electronic keyboard 61 keys", "portable keyboard piano", "arranger keyboard"],
                min_price_usd=60, family="electronic"),
    CategorySpec("modern", "drum_pad",
                ["drum pad controller", "mpc drum pad", "sampler pad", "finger drum pad"],
                min_price_usd=80, family="electronic"),

    CategorySpec("modern", "midi_keyboard",
                ["MIDI keyboard controller", "MIDI keyboard 49 keys", "MIDI keyboard 25 keys", "akai midi keyboard"],
                min_price_usd=80, family="midi_controller"),
    CategorySpec("modern", "launchpad",
                ["Novation Launchpad", "ableton launchpad", "grid controller"],
                min_price_usd=80, family="midi_controller"),
    CategorySpec("modern", "midi_guitar",
                ["MIDI guitar controller", "jamstik MIDI guitar", "guitar to MIDI"],
                min_price_usd=200, family="midi_controller"),

    CategorySpec("modern", "electric_violin",
                ["electric violin", "silent violin", "yamaha electric violin"],
                min_price_usd=100, family="electro_acoustic"),
    CategorySpec("modern", "silent_piano",
                ["silent digital piano", "hybrid piano", "disklavier piano"],
                min_price_usd=500, family="electro_acoustic"),

    CategorySpec("modern", "smart_guitar",
                ["smart guitar", "Populele", "smart ukulele LED", "AI guitar"],
                is_smart=True, min_price_usd=60, family="smart"),
    CategorySpec("modern", "smart_piano",
                ["smart piano", "AI keyboard", "TheONE smart piano", "LED keyboard learning"],
                is_smart=True, min_price_usd=80, family="smart"),
    CategorySpec("modern", "smart_drum",
                ["smart drum pad", "AI drum practice", "LED drum pad"],
                is_smart=True, min_price_usd=40, family="smart"),
]


def all_queries():
    """[(category, subcategory, query, is_smart), ...]"""
    out = []
    for spec in CATEGORIES:
        for q in spec.queries:
            out.append((spec.category, spec.subcategory, q, spec.is_smart))
    return out


def queries_for_subcategory(subcategory: str):
    for spec in CATEGORIES:
        if spec.subcategory == subcategory:
            return [(spec.category, spec.subcategory, q, spec.is_smart) for q in spec.queries]
    return []


def spec_for_subcategory(subcategory: str) -> "CategorySpec | None":
    for spec in CATEGORIES:
        if spec.subcategory == subcategory:
            return spec
    return None


def min_price_for(subcategory: str) -> float:
    spec = spec_for_subcategory(subcategory)
    return spec.min_price_usd if spec else 0.0


def family_for(subcategory: str) -> str:
    spec = spec_for_subcategory(subcategory)
    return spec.family if spec else ""


SUBCATEGORIES = [s.subcategory for s in CATEGORIES]
