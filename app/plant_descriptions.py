from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy import select

from .db import SessionLocal
from .models import Plant


LANGS = ("en", "ru", "de", "fr", "es", "it", "pt", "pl", "zh")


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", str(value or "").casefold()).strip()


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Short customer-facing descriptions. They intentionally describe flavour,
# texture and common culinary use without making health/medical claims.
DESCRIPTIONS: dict[str, dict[str, str]] = {
    "mizuna": {
        "en": "Mizuna microgreens have tender leaves and a fresh, mildly peppery mustard flavour. They work well in salads, sandwiches and as a bright garnish.",
        "ru": "Микрозелень мизуны отличается нежными листьями и свежим, мягко-пряным горчичным вкусом. Хорошо подходит для салатов, сэндвичей и яркого украшения блюд.",
        "de": "Mizuna-Microgreens haben zarte Blätter und einen frischen, mild pfeffrig-senfigen Geschmack. Sie passen gut zu Salaten, Sandwiches und als frische Garnitur.",
        "fr": "Les micropousses de mizuna ont des feuilles tendres et une saveur fraîche, légèrement poivrée et moutardée. Elles conviennent aux salades, sandwichs et garnitures.",
        "es": "Los microbrotes de mizuna tienen hojas tiernas y un sabor fresco, suavemente picante y a mostaza. Son ideales para ensaladas, bocadillos y como guarnición.",
        "it": "I microgreens di mizuna hanno foglie tenere e un gusto fresco, leggermente pepato e senapato. Sono ottimi in insalate, panini e come guarnizione.",
        "pt": "Os microverdes de mizuna têm folhas tenras e sabor fresco, levemente picante e com nota de mostarda. Combinam bem com saladas, sanduíches e guarnições.",
        "pl": "Mikrolistki mizuny mają delikatne liście i świeży, lekko pieprzny, musztardowy smak. Pasują do sałatek, kanapek i jako dekoracja potraw.",
        "zh": "水菜微型蔬菜叶片细嫩，味道清新，带有轻微胡椒和芥末风味。适合加入沙拉、三明治，也可作为菜肴点缀。",
    },
    "cilantro": {
        "en": "Cilantro microgreens have a vivid fresh aroma with citrus and herbal notes. Their distinctive flavour is especially good in salads, tacos, bowls and Asian-style dishes.",
        "ru": "Микрозелень кинзы обладает ярким свежим ароматом с цитрусовыми и травянистыми нотами. Её характерный вкус хорошо подходит для салатов, тако, боулов и блюд азиатской кухни.",
        "de": "Koriander-Microgreens besitzen ein intensives frisches Aroma mit Zitrus- und Kräuternoten. Ihr charakteristischer Geschmack passt besonders gut zu Salaten, Tacos, Bowls und asiatischen Gerichten.",
        "fr": "Les micropousses de coriandre offrent un arôme frais et intense, avec des notes d’agrumes et d’herbes. Leur goût caractéristique convient aux salades, tacos, bowls et plats asiatiques.",
        "es": "Los microbrotes de cilantro tienen un aroma fresco e intenso con notas cítricas y herbales. Su sabor característico combina muy bien con ensaladas, tacos, bowls y platos asiáticos.",
        "it": "I microgreens di coriandolo hanno un aroma fresco e intenso con note agrumate ed erbacee. Il loro gusto caratteristico si abbina bene a insalate, tacos, bowl e piatti asiatici.",
        "pt": "Os microverdes de coentro têm aroma fresco e marcante, com notas cítricas e herbais. O sabor característico combina bem com saladas, tacos, bowls e pratos asiáticos.",
        "pl": "Mikrolistki kolendry mają wyrazisty, świeży aromat z nutami cytrusowymi i ziołowymi. Charakterystyczny smak dobrze pasuje do sałatek, tacos, bowli i dań azjatyckich.",
        "zh": "香菜微型蔬菜香气清新浓郁，带有柑橘和草本气息。独特风味很适合沙拉、塔可、能量碗和亚洲风味菜肴。",
    },
    "kohlrabi": {
        "en": "Kohlrabi microgreens are tender and crisp with a mild cabbage flavour and a light sweetness. They are easy to pair with salads, sandwiches and vegetable dishes.",
        "ru": "Микрозелень кольраби нежная и хрустящая, с мягким капустным вкусом и лёгкой сладостью. Хорошо сочетается с салатами, сэндвичами и овощными блюдами.",
        "de": "Kohlrabi-Microgreens sind zart und knackig, mit mildem Kohlgeschmack und leichter Süße. Sie passen gut zu Salaten, Sandwiches und Gemüsegerichten.",
        "fr": "Les micropousses de chou-rave sont tendres et croquantes, avec une douce saveur de chou et une légère note sucrée. Elles accompagnent bien salades, sandwichs et plats de légumes.",
        "es": "Los microbrotes de colirrábano son tiernos y crujientes, con un suave sabor a col y un toque dulce. Combinan bien con ensaladas, bocadillos y platos de verduras.",
        "it": "I microgreens di cavolo rapa sono teneri e croccanti, con un delicato sapore di cavolo e una leggera dolcezza. Si abbinano bene a insalate, panini e piatti di verdure.",
        "pt": "Os microverdes de couve-rábano são tenros e crocantes, com sabor suave de couve e leve doçura. Combinam bem com saladas, sanduíches e pratos de legumes.",
        "pl": "Mikrolistki kalarepy są delikatne i chrupiące, mają łagodny kapuściany smak z lekką słodyczą. Dobrze pasują do sałatek, kanapek i dań warzywnych.",
        "zh": "苤蓝微型蔬菜口感细嫩爽脆，带有温和的甘蓝风味和淡淡甜味。适合搭配沙拉、三明治和蔬菜料理。",
    },
    "cress": {
        "en": "Cress microgreens are delicate but noticeably peppery, with a clean, spicy finish. They add character to sandwiches, salads, eggs and cold appetisers.",
        "ru": "Микрозелень кресс-салата нежная, но заметно пряная, с чистым перечным послевкусием. Она добавляет выразительности сэндвичам, салатам, блюдам из яиц и холодным закускам.",
        "de": "Kresse-Microgreens sind zart, aber deutlich würzig und pfeffrig. Sie geben Sandwiches, Salaten, Eierspeisen und kalten Vorspeisen mehr Charakter.",
        "fr": "Les micropousses de cresson sont délicates mais nettement poivrées, avec une finale fraîche et épicée. Elles relèvent sandwichs, salades, œufs et entrées froides.",
        "es": "Los microbrotes de berro son delicados pero claramente picantes, con un final fresco y a pimienta. Aportan carácter a bocadillos, ensaladas, huevos y entrantes fríos.",
        "it": "I microgreens di crescione sono delicati ma decisamente pepati, con un finale fresco e speziato. Danno carattere a panini, insalate, uova e antipasti freddi.",
        "pt": "Os microverdes de agrião são delicados, mas nitidamente picantes e apimentados. Dão mais personalidade a sanduíches, saladas, ovos e entradas frias.",
        "pl": "Mikrolistki rzeżuchy są delikatne, ale wyraźnie pikantne i pieprzne. Dodają charakteru kanapkom, sałatkom, jajkom i zimnym przekąskom.",
        "zh": "水芹类微型蔬菜口感细嫩，但有明显的胡椒辛香和清爽辣味。很适合搭配三明治、沙拉、鸡蛋和冷盘。",
    },
    "radish": {
        "en": "Radish microgreens are juicy and crisp with a recognisable peppery radish flavour. They are excellent in salads, sandwiches, bowls and savoury snacks.",
        "ru": "Микрозелень редиса сочная и хрустящая, с узнаваемым пряным вкусом редиса. Отлично подходит для салатов, сэндвичей, боулов и несладких закусок.",
        "de": "Radieschen-Microgreens sind saftig und knackig, mit dem typischen pfeffrigen Radieschengeschmack. Sie eignen sich hervorragend für Salate, Sandwiches, Bowls und herzhafte Snacks.",
        "fr": "Les micropousses de radis sont juteuses et croquantes, avec la saveur poivrée caractéristique du radis. Elles sont parfaites dans les salades, sandwichs, bowls et en-cas salés.",
        "es": "Los microbrotes de rábano son jugosos y crujientes, con el característico sabor picante del rábano. Van muy bien en ensaladas, bocadillos, bowls y aperitivos salados.",
        "it": "I microgreens di ravanello sono succosi e croccanti, con il tipico gusto pepato del ravanello. Sono ottimi in insalate, panini, bowl e snack salati.",
        "pt": "Os microverdes de rabanete são suculentos e crocantes, com o sabor picante característico do rabanete. Ficam ótimos em saladas, sanduíches, bowls e petiscos salgados.",
        "pl": "Mikrolistki rzodkiewki są soczyste i chrupiące, z charakterystycznym pieprznym smakiem rzodkiewki. Świetnie pasują do sałatek, kanapek, bowli i wytrawnych przekąsek.",
        "zh": "萝卜微型蔬菜多汁爽脆，带有典型的萝卜辛香。很适合用于沙拉、三明治、能量碗和咸味小食。",
    },
    "china_rose": {
        "en": "China Rose radish microgreens are crisp and colourful, with a fresh peppery flavour typical of radish. They make salads, sandwiches and plated dishes look especially lively.",
        "ru": "Микрозелень редиса Китайская Роза хрустящая и яркая, со свежим характерным для редиса пряным вкусом. Она особенно хорошо смотрится в салатах, сэндвичах и при подаче готовых блюд.",
        "de": "China-Rose-Radieschen-Microgreens sind knackig und farbenfroh, mit einem frischen, typisch pfeffrigen Radieschengeschmack. Sie bringen Farbe in Salate, Sandwiches und angerichtete Speisen.",
        "fr": "Les micropousses de radis China Rose sont croquantes et colorées, avec une saveur fraîche et poivrée typique du radis. Elles apportent une belle touche aux salades, sandwichs et assiettes.",
        "es": "Los microbrotes de rábano China Rose son crujientes y coloridos, con un sabor fresco y picante típico del rábano. Dan un aspecto muy vivo a ensaladas, bocadillos y platos servidos.",
        "it": "I microgreens di ravanello China Rose sono croccanti e colorati, con un gusto fresco e pepato tipico del ravanello. Rendono più vivaci insalate, panini e piatti serviti.",
        "pt": "Os microverdes de rabanete China Rose são crocantes e coloridos, com sabor fresco e picante típico do rabanete. Dão um toque vivo a saladas, sanduíches e pratos montados.",
        "pl": "Mikrolistki rzodkiewki China Rose są chrupiące i barwne, o świeżym, typowo pieprznym smaku rzodkiewki. Świetnie ożywiają sałatki, kanapki i gotowe dania.",
        "zh": "China Rose 萝卜微型蔬菜爽脆、色泽鲜明，带有典型萝卜的清新辛香。用于沙拉、三明治和摆盘时尤其亮眼。",
    },
    "daikon": {
        "en": "Daikon microgreens are fresh and crisp with a clean, moderately peppery radish taste. They pair well with salads, rice dishes, sandwiches and Asian-style food.",
        "ru": "Микрозелень редьки свежая и хрустящая, с чистым, умеренно пряным вкусом редиса. Хорошо подходит для салатов, блюд с рисом, сэндвичей и азиатской кухни.",
        "de": "Rettich-Microgreens sind frisch und knackig, mit einem klaren, mäßig pfeffrigen Rettichgeschmack. Sie passen zu Salaten, Reisgerichten, Sandwiches und asiatischen Speisen.",
        "fr": "Les micropousses de daikon sont fraîches et croquantes, avec une saveur de radis nette et modérément poivrée. Elles s’accordent avec salades, riz, sandwichs et cuisine asiatique.",
        "es": "Los microbrotes de daikon son frescos y crujientes, con un sabor limpio y moderadamente picante a rábano. Combinan con ensaladas, arroz, bocadillos y cocina asiática.",
        "it": "I microgreens di daikon sono freschi e croccanti, con un gusto pulito e moderatamente pepato di ravanello. Si abbinano a insalate, riso, panini e piatti asiatici.",
        "pt": "Os microverdes de daikon são frescos e crocantes, com sabor limpo e moderadamente picante de rabanete. Combinam com saladas, arroz, sanduíches e pratos asiáticos.",
        "pl": "Mikrolistki daikonu są świeże i chrupiące, o czystym, umiarkowanie pikantnym smaku rzodkwi. Pasują do sałatek, ryżu, kanapek i dań azjatyckich.",
        "zh": "白萝卜微型蔬菜清新爽脆，萝卜风味干净并带有适度辛香。适合搭配沙拉、米饭、三明治和亚洲风味料理。",
    },
    "turnip": {
        "en": "Turnip microgreens are tender with a mild brassica flavour, a light sweetness and a gentle mustard note. They fit easily into salads, sandwiches and vegetable dishes.",
        "ru": "Микрозелень репы нежная, с мягким капустным вкусом, лёгкой сладостью и деликатной горчичной ноткой. Хорошо подходит для салатов, сэндвичей и овощных блюд.",
        "de": "Rüben-Microgreens sind zart, mit mildem Kohlgeschmack, leichter Süße und einer feinen Senfnote. Sie passen gut zu Salaten, Sandwiches und Gemüsegerichten.",
        "fr": "Les micropousses de navet sont tendres, avec une douce saveur de crucifère, une légère sucrosité et une petite note de moutarde. Elles conviennent aux salades, sandwichs et plats de légumes.",
        "es": "Los microbrotes de nabo son tiernos, con un suave sabor a crucíferas, un ligero dulzor y una delicada nota de mostaza. Van bien con ensaladas, bocadillos y platos de verduras.",
        "it": "I microgreens di rapa sono teneri, con un delicato gusto di brassica, una lieve dolcezza e una leggera nota di senape. Si adattano bene a insalate, panini e piatti di verdure.",
        "pt": "Os microverdes de nabo são tenros, com sabor suave de brássica, leve doçura e uma delicada nota de mostarda. Combinam com saladas, sanduíches e pratos de legumes.",
        "pl": "Mikrolistki rzepy są delikatne, o łagodnym kapuścianym smaku, lekkiej słodyczy i subtelnej nucie musztardowej. Pasują do sałatek, kanapek i dań warzywnych.",
        "zh": "芜菁微型蔬菜口感细嫩，带有温和的十字花科风味、淡淡甜味和轻微芥末香。适合沙拉、三明治和蔬菜料理。",
    },
    "arugula": {
        "en": "Arugula microgreens have a distinctive nutty, peppery flavour and tender texture. They are a natural match for salads, sandwiches, pizza and pasta.",
        "ru": "Микрозелень рукколы обладает узнаваемым орехово-пряным вкусом и нежной текстурой. Отлично сочетается с салатами, сэндвичами, пиццей и пастой.",
        "de": "Rucola-Microgreens haben einen typischen nussig-pfeffrigen Geschmack und eine zarte Textur. Sie passen hervorragend zu Salaten, Sandwiches, Pizza und Pasta.",
        "fr": "Les micropousses de roquette ont une saveur caractéristique, à la fois noisettée et poivrée, avec une texture tendre. Elles sont idéales avec salades, sandwichs, pizzas et pâtes.",
        "es": "Los microbrotes de rúcula tienen un sabor característico, entre nuez y pimienta, y una textura tierna. Combinan perfectamente con ensaladas, bocadillos, pizza y pasta.",
        "it": "I microgreens di rucola hanno un caratteristico gusto nocciolato e pepato e una consistenza tenera. Sono perfetti con insalate, panini, pizza e pasta.",
        "pt": "Os microverdes de rúcula têm sabor característico, levemente amendoado e apimentado, com textura tenra. Combinam muito bem com saladas, sanduíches, pizza e massa.",
        "pl": "Mikrolistki rukoli mają charakterystyczny orzechowo-pieprzny smak i delikatną teksturę. Świetnie pasują do sałatek, kanapek, pizzy i makaronów.",
        "zh": "芝麻菜微型蔬菜具有独特的坚果和胡椒风味，口感细嫩。非常适合搭配沙拉、三明治、披萨和意面。",
    },
    "rapini": {
        "en": "Rapini microgreens have a fresh brassica flavour with a pleasant mustard-like bitterness and gentle spice. They pair well with salads, sandwiches and Mediterranean-style dishes.",
        "ru": "Микрозелень рапини имеет свежий капустный вкус с приятной горчичной горчинкой и лёгкой остротой. Хорошо сочетается с салатами, сэндвичами и блюдами средиземноморской кухни.",
        "de": "Rapini-Microgreens haben einen frischen Kohlgeschmack mit angenehmer senfiger Bitternote und milder Würze. Sie passen zu Salaten, Sandwiches und mediterranen Gerichten.",
        "fr": "Les micropousses de rapini ont une saveur fraîche de crucifère, avec une agréable amertume moutardée et une légère note épicée. Elles conviennent aux salades, sandwichs et plats méditerranéens.",
        "es": "Los microbrotes de rapini tienen un sabor fresco a crucíferas, con un agradable amargor tipo mostaza y un ligero toque picante. Combinan con ensaladas, bocadillos y platos mediterráneos.",
        "it": "I microgreens di rapini hanno un fresco gusto di brassica, con una piacevole nota amarognola di senape e una lieve piccantezza. Si abbinano a insalate, panini e piatti mediterranei.",
        "pt": "Os microverdes de rapini têm sabor fresco de brássica, com agradável amargor de mostarda e leve picância. Combinam com saladas, sanduíches e pratos mediterrânicos.",
        "pl": "Mikrolistki rapini mają świeży kapuściany smak z przyjemną musztardową goryczką i lekką pikantnością. Pasują do sałatek, kanapek i dań śródziemnomorskich.",
        "zh": "意大利芥蓝（Rapini）微型蔬菜带有清新的十字花科风味、舒适的芥末微苦和轻微辛辣感。适合沙拉、三明治和地中海风味菜肴。",
    },
    "mustard": {
        "en": "Mustard microgreens are aromatic and lively, with a clear mustard heat that becomes brighter as you chew. They add a spicy accent to salads, sandwiches and savoury dishes.",
        "ru": "Микрозелень горчицы ароматная и яркая, с хорошо заметной горчичной остротой. Она добавляет пряный акцент салатам, сэндвичам и несладким блюдам.",
        "de": "Senf-Microgreens sind aromatisch und lebhaft, mit einer deutlichen Senfschärfe. Sie geben Salaten, Sandwiches und herzhaften Gerichten eine würzige Note.",
        "fr": "Les micropousses de moutarde sont aromatiques et vives, avec une chaleur moutardée bien présente. Elles apportent une note épicée aux salades, sandwichs et plats salés.",
        "es": "Los microbrotes de mostaza son aromáticos y vivos, con un picante de mostaza claramente perceptible. Aportan un toque especiado a ensaladas, bocadillos y platos salados.",
        "it": "I microgreens di senape sono aromatici e vivaci, con una piccantezza di senape ben riconoscibile. Aggiungono una nota speziata a insalate, panini e piatti salati.",
        "pt": "Os microverdes de mostarda são aromáticos e intensos, com picância de mostarda bem perceptível. Acrescentam um toque picante a saladas, sanduíches e pratos salgados.",
        "pl": "Mikrolistki gorczycy są aromatyczne i wyraziste, z dobrze wyczuwalną musztardową ostrością. Dodają pikantnego akcentu sałatkom, kanapkom i wytrawnym daniom.",
        "zh": "芥菜微型蔬菜香气鲜明，带有清晰的芥末辛辣感。可以为沙拉、三明治和咸味料理增添活泼的辛香。",
    },
}


ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("china_rose", ("china rose", "чайна роуз", "китайская роза")),
    ("rapini", ("rapini", "рапини")),
    ("mustard", ("mustard", "горчица")),
    ("mizuna", ("mizuna", "мизуна")),
    ("cilantro", ("cilantro", "coriander", "кинза", "кориандр")),
    ("kohlrabi", ("kohlrabi", "кольраби")),
    ("cress", ("cress", "кресс")),
    ("arugula", ("arugula", "rocket", "rucola", "руккола")),
    ("turnip", ("turnip", "репа")),
    ("daikon", ("daikon", "редька")),
    ("radish", ("radish", "редис")),
)


def _plant_key(plant: Plant) -> str | None:
    values = [plant.code]
    if isinstance(plant.names, Mapping):
        values.extend(str(value) for value in plant.names.values() if value)
    haystack = " | ".join(_norm(value) for value in values)
    for key, aliases in ALIASES:
        if any(_norm(alias) in haystack for alias in aliases):
            return key
    return None


def _generic_description(name: str, lang: str) -> str:
    templates = {
        "en": "{name} microgreens are grown for a tender texture and fresh, concentrated flavour. They are a convenient addition to salads, sandwiches, bowls and finished dishes.",
        "ru": "Микрозелень «{name}» выращивается ради нежной текстуры и свежего концентрированного вкуса. Её удобно добавлять в салаты, сэндвичи, боулы и готовые блюда.",
        "de": "{name}-Microgreens werden wegen ihrer zarten Textur und ihres frischen, konzentrierten Geschmacks angebaut. Sie eignen sich für Salate, Sandwiches, Bowls und fertige Gerichte.",
        "fr": "Les micropousses de {name} sont cultivées pour leur texture tendre et leur saveur fraîche et concentrée. Elles s’ajoutent facilement aux salades, sandwichs, bowls et plats finis.",
        "es": "Los microbrotes de {name} se cultivan por su textura tierna y su sabor fresco y concentrado. Son fáciles de añadir a ensaladas, bocadillos, bowls y platos terminados.",
        "it": "I microgreens di {name} vengono coltivati per la consistenza tenera e il gusto fresco e concentrato. Sono facili da aggiungere a insalate, panini, bowl e piatti pronti.",
        "pt": "Os microverdes de {name} são cultivados pela textura tenra e pelo sabor fresco e concentrado. São fáceis de acrescentar a saladas, sanduíches, bowls e pratos prontos.",
        "pl": "Mikrolistki {name} są uprawiane dla delikatnej tekstury i świeżego, skoncentrowanego smaku. Łatwo dodać je do sałatek, kanapek, bowli i gotowych dań.",
        "zh": "{name}微型蔬菜以细嫩口感和清新浓郁的风味为特点。适合加入沙拉、三明治、能量碗和各类成品菜肴。",
    }
    return templates[lang].format(name=name)


def _localized_name(plant: Plant, lang: str) -> str:
    names = plant.names if isinstance(plant.names, Mapping) else {}
    return str(names.get(lang) or names.get("en") or names.get("ru") or plant.code or "Plant")


async def ensure_plant_descriptions() -> int:
    """Fill only missing description translations for every existing plant.

    Known plants receive a tailored description. Any other plant gets a neutral
    generic description using its localized name, so every language always has
    usable content. Existing administrator-written text is never overwritten.
    """
    changed = 0
    async with SessionLocal() as session:
        plants = (await session.execute(select(Plant))).scalars().all()
        for plant in plants:
            current = dict(plant.descriptions or {})
            key = _plant_key(plant)
            specific = DESCRIPTIONS.get(key or "", {})
            modified = False
            for lang in LANGS:
                if str(current.get(lang) or "").strip():
                    continue
                current[lang] = specific.get(lang) or _generic_description(
                    _localized_name(plant, lang), lang
                )
                modified = True
            if modified:
                plant.descriptions = current
                plant.updated_at = _now_naive()
                changed += 1
        if changed:
            await session.commit()
    if changed:
        print(f"[plants] multilingual descriptions populated for {changed} plant(s)")
    return changed
