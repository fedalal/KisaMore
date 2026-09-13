from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from .db import SessionLocal
from .models import Plant
from .plant_descriptions import LANGS, _localized_name, _plant_key


TARGET_FACTS = 20


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


PROFILES = {
    "mizuna": {
        "family": "brassicaceae",
        "species": "Brassica rapa var. nipposinica",
        "origin": "japan",
        "flavor": "mild_mustard",
        "color": "fine_green",
        "relatives": "brassica",
    },
    "cilantro": {
        "family": "apiaceae",
        "species": "Coriandrum sativum",
        "origin": "med_west_asia",
        "flavor": "citrus_herbal",
        "color": "soft_green",
        "relatives": "carrot_parsley",
    },
    "kohlrabi": {
        "family": "brassicaceae",
        "species": "Brassica oleracea, Gongylodes Group",
        "origin": "europe",
        "flavor": "mild_cabbage",
        "color": "green_purple",
        "relatives": "cabbage_broccoli",
    },
    "cress": {
        "family": "brassicaceae",
        "species": "Lepidium sativum",
        "origin": "west_asia_africa",
        "flavor": "peppery",
        "color": "bright_green",
        "relatives": "mustard_radish",
    },
    "radish": {
        "family": "brassicaceae",
        "species": "Raphanus sativus",
        "origin": "old_world",
        "flavor": "radish_peppery",
        "color": "green_colored_stem",
        "relatives": "mustard_radish",
    },
    "china_rose": {
        "family": "brassicaceae",
        "species": "Raphanus sativus",
        "origin": "east_asia",
        "flavor": "radish_peppery",
        "color": "pink_green",
        "relatives": "mustard_radish",
    },
    "daikon": {
        "family": "brassicaceae",
        "species": "Raphanus sativus var. longipinnatus",
        "origin": "east_asia",
        "flavor": "clean_radish",
        "color": "bright_green",
        "relatives": "mustard_radish",
    },
    "turnip": {
        "family": "brassicaceae",
        "species": "Brassica rapa subsp. rapa",
        "origin": "europe_west_asia",
        "flavor": "mild_turnip",
        "color": "fresh_green",
        "relatives": "brassica",
    },
    "arugula": {
        "family": "brassicaceae",
        "species": "Eruca vesicaria",
        "origin": "mediterranean",
        "flavor": "peppery_nutty",
        "color": "fresh_green",
        "relatives": "mustard_radish",
    },
    "rapini": {
        "family": "brassicaceae",
        "species": "Brassica rapa, Ruvo Group",
        "origin": "mediterranean",
        "flavor": "bitter_mustard",
        "color": "fresh_green",
        "relatives": "brassica",
    },
    "mustard": {
        "family": "brassicaceae",
        "species": "Brassica / Sinapis group",
        "origin": "asia_europe",
        "flavor": "mustard_spicy",
        "color": "fresh_green",
        "relatives": "mustard_radish",
    },
}


WORDS = {
    "en": {
        "family": {"brassicaceae": "the cabbage family (Brassicaceae)", "apiaceae": "the carrot family (Apiaceae)", "unknown": "a botanical family defined by its variety"},
        "origin": {"japan": "Japan and East Asia", "med_west_asia": "the Mediterranean region and western Asia", "europe": "Europe", "west_asia_africa": "western Asia and northeastern Africa", "old_world": "the Old World, with a long history of cultivation in Asia and Europe", "east_asia": "East Asia", "europe_west_asia": "Europe and western Asia", "mediterranean": "the Mediterranean region", "asia_europe": "Asia and Europe", "unknown": "a long cultivation history that depends on the variety"},
        "flavor": {"mild_mustard": "fresh and mildly mustard-like", "citrus_herbal": "bright, citrusy and herbal", "mild_cabbage": "mildly cabbage-like with a touch of sweetness", "peppery": "clean and peppery", "radish_peppery": "crisp and distinctly radish-peppery", "clean_radish": "fresh, clean and moderately radish-peppery", "mild_turnip": "mild, fresh and gently brassica-like", "peppery_nutty": "peppery with a light nutty note", "bitter_mustard": "pleasantly bitter with a mustard note", "mustard_spicy": "mustardy and spicy", "unknown": "fresh and concentrated"},
        "color": {"fine_green": "fine, feathery green leaves", "soft_green": "delicate green shoots", "green_purple": "green shoots that can show purple tones", "bright_green": "bright green shoots", "green_colored_stem": "green leaves with stems that may show extra colour", "pink_green": "green leaves with vivid pink-to-purple stems", "fresh_green": "fresh green shoots", "unknown": "young green shoots"},
        "relatives": {"brassica": "cabbage, turnip and mustard", "carrot_parsley": "carrot and parsley", "cabbage_broccoli": "cabbage, broccoli and kale", "mustard_radish": "mustard, radish and other brassicas", "unknown": "other edible plants in its botanical group"},
    },
    "ru": {
        "family": {"brassicaceae": "семейству капустных (Brassicaceae)", "apiaceae": "семейству зонтичных (Apiaceae)", "unknown": "ботаническому семейству, которое определяется сортом"},
        "origin": {"japan": "Японией и Восточной Азией", "med_west_asia": "Средиземноморьем и Западной Азией", "europe": "Европой", "west_asia_africa": "Западной Азией и северо-востоком Африки", "old_world": "Старым Светом и многовековым выращиванием в Азии и Европе", "east_asia": "Восточной Азией", "europe_west_asia": "Европой и Западной Азией", "mediterranean": "Средиземноморьем", "asia_europe": "Азией и Европой", "unknown": "долгой историей выращивания, зависящей от сорта"},
        "flavor": {"mild_mustard": "свежий и мягко-горчичный", "citrus_herbal": "яркий, цитрусово-травянистый", "mild_cabbage": "мягкий капустный с лёгкой сладостью", "peppery": "чистый и перечный", "radish_peppery": "хрустящий и узнаваемо пряный, как у редиса", "clean_radish": "свежий и умеренно пряный, как у редьки", "mild_turnip": "мягкий, свежий и слегка капустный", "peppery_nutty": "перечный с лёгкой ореховой нотой", "bitter_mustard": "приятно горьковатый с горчичной нотой", "mustard_spicy": "горчичный и пикантный", "unknown": "свежий и концентрированный"},
        "color": {"fine_green": "тонкие резные зелёные листья", "soft_green": "нежные зелёные побеги", "green_purple": "зелёные побеги, иногда с фиолетовыми оттенками", "bright_green": "ярко-зелёные побеги", "green_colored_stem": "зелёные листья со стеблями, которые могут быть окрашены", "pink_green": "зелёные листья с яркими розово-фиолетовыми стеблями", "fresh_green": "свежие зелёные побеги", "unknown": "молодые зелёные побеги"},
        "relatives": {"brassica": "капуста, репа и горчица", "carrot_parsley": "морковь и петрушка", "cabbage_broccoli": "капуста, брокколи и кейл", "mustard_radish": "горчица, редис и другие капустные", "unknown": "другие съедобные растения своей ботанической группы"},
    },
    "de": {
        "family": {"brassicaceae": "zur Familie der Kreuzblütler (Brassicaceae)", "apiaceae": "zur Familie der Doldenblütler (Apiaceae)", "unknown": "zu einer sortenabhängigen botanischen Familie"},
        "origin": {"japan": "Japan und Ostasien", "med_west_asia": "den Mittelmeerraum und Westasien", "europe": "Europa", "west_asia_africa": "Westasien und Nordostafrika", "old_world": "die Alte Welt mit langer Anbaugeschichte in Asien und Europa", "east_asia": "Ostasien", "europe_west_asia": "Europa und Westasien", "mediterranean": "den Mittelmeerraum", "asia_europe": "Asien und Europa", "unknown": "eine lange, sortenabhängige Anbaugeschichte"},
        "flavor": {"mild_mustard": "frisch und mild senfig", "citrus_herbal": "frisch, zitrusartig und kräuterig", "mild_cabbage": "mild kohlartig mit leichter Süße", "peppery": "klar und pfeffrig", "radish_peppery": "knackig und typisch radieschen-scharf", "clean_radish": "frisch und mäßig rettich-scharf", "mild_turnip": "mild, frisch und leicht kohlartig", "peppery_nutty": "pfeffrig mit leichter nussiger Note", "bitter_mustard": "angenehm bitter mit Senfnote", "mustard_spicy": "senfig und würzig", "unknown": "frisch und konzentriert"},
        "color": {"fine_green": "feine, gefiederte grüne Blätter", "soft_green": "zarte grüne Triebe", "green_purple": "grüne Triebe mit möglichen violetten Tönen", "bright_green": "leuchtend grüne Triebe", "green_colored_stem": "grüne Blätter mit teils farbigen Stielen", "pink_green": "grüne Blätter mit kräftig rosa-violetten Stielen", "fresh_green": "frische grüne Triebe", "unknown": "junge grüne Triebe"},
        "relatives": {"brassica": "Kohl, Rübe und Senf", "carrot_parsley": "Karotte und Petersilie", "cabbage_broccoli": "Kohl, Brokkoli und Grünkohl", "mustard_radish": "Senf, Radieschen und andere Kreuzblütler", "unknown": "andere essbare Pflanzen derselben botanischen Gruppe"},
    },
    "fr": {
        "family": {"brassicaceae": "à la famille des Brassicacées", "apiaceae": "à la famille des Apiacées", "unknown": "à une famille botanique déterminée par la variété"},
        "origin": {"japan": "le Japon et l’Asie de l’Est", "med_west_asia": "la Méditerranée et l’Asie occidentale", "europe": "l’Europe", "west_asia_africa": "l’Asie occidentale et le nord-est de l’Afrique", "old_world": "l’Ancien Monde, avec une longue culture en Asie et en Europe", "east_asia": "l’Asie de l’Est", "europe_west_asia": "l’Europe et l’Asie occidentale", "mediterranean": "la région méditerranéenne", "asia_europe": "l’Asie et l’Europe", "unknown": "une longue histoire de culture qui dépend de la variété"},
        "flavor": {"mild_mustard": "frais et doucement moutardé", "citrus_herbal": "vif, citronné et herbacé", "mild_cabbage": "doux, rappelant le chou, avec une légère sucrosité", "peppery": "net et poivré", "radish_peppery": "croquant et typiquement poivré comme le radis", "clean_radish": "frais et modérément poivré comme le radis", "mild_turnip": "doux, frais et légèrement brassicacé", "peppery_nutty": "poivré avec une légère note de noisette", "bitter_mustard": "agréablement amer avec une note de moutarde", "mustard_spicy": "moutardé et relevé", "unknown": "frais et concentré"},
        "color": {"fine_green": "de fines feuilles vertes découpées", "soft_green": "de délicates pousses vertes", "green_purple": "des pousses vertes pouvant prendre des tons violets", "bright_green": "des pousses vert vif", "green_colored_stem": "des feuilles vertes avec des tiges parfois colorées", "pink_green": "des feuilles vertes sur des tiges rose-violet vif", "fresh_green": "des pousses vertes fraîches", "unknown": "de jeunes pousses vertes"},
        "relatives": {"brassica": "le chou, le navet et la moutarde", "carrot_parsley": "la carotte et le persil", "cabbage_broccoli": "le chou, le brocoli et le kale", "mustard_radish": "la moutarde, le radis et d’autres Brassicacées", "unknown": "d’autres plantes comestibles de son groupe botanique"},
    },
    "es": {
        "family": {"brassicaceae": "a la familia de las brasicáceas (Brassicaceae)", "apiaceae": "a la familia de las apiáceas (Apiaceae)", "unknown": "a una familia botánica que depende de la variedad"},
        "origin": {"japan": "Japón y Asia oriental", "med_west_asia": "el Mediterráneo y Asia occidental", "europe": "Europa", "west_asia_africa": "Asia occidental y el noreste de África", "old_world": "el Viejo Mundo, con una larga historia de cultivo en Asia y Europa", "east_asia": "Asia oriental", "europe_west_asia": "Europa y Asia occidental", "mediterranean": "la región mediterránea", "asia_europe": "Asia y Europa", "unknown": "una larga historia de cultivo que depende de la variedad"},
        "flavor": {"mild_mustard": "fresco y suavemente mostazado", "citrus_herbal": "vivo, cítrico y herbal", "mild_cabbage": "suave, parecido a la col, con un toque dulce", "peppery": "limpio y picante", "radish_peppery": "crujiente y claramente picante como el rábano", "clean_radish": "fresco y moderadamente picante como el rábano", "mild_turnip": "suave, fresco y ligeramente parecido a la col", "peppery_nutty": "picante con una ligera nota de nuez", "bitter_mustard": "agradablemente amargo con una nota de mostaza", "mustard_spicy": "mostazado y picante", "unknown": "fresco y concentrado"},
        "color": {"fine_green": "hojas verdes finas y recortadas", "soft_green": "brotes verdes delicados", "green_purple": "brotes verdes que pueden mostrar tonos morados", "bright_green": "brotes verde brillante", "green_colored_stem": "hojas verdes con tallos que pueden tener color", "pink_green": "hojas verdes con tallos rosa-violeta vivos", "fresh_green": "brotes verdes frescos", "unknown": "brotes verdes jóvenes"},
        "relatives": {"brassica": "la col, el nabo y la mostaza", "carrot_parsley": "la zanahoria y el perejil", "cabbage_broccoli": "la col, el brócoli y la kale", "mustard_radish": "la mostaza, el rábano y otras brasicáceas", "unknown": "otras plantas comestibles de su grupo botánico"},
    },
    "it": {
        "family": {"brassicaceae": "alla famiglia delle Brassicaceae", "apiaceae": "alla famiglia delle Apiaceae", "unknown": "a una famiglia botanica definita dalla varietà"},
        "origin": {"japan": "il Giappone e l’Asia orientale", "med_west_asia": "il Mediterraneo e l’Asia occidentale", "europe": "l’Europa", "west_asia_africa": "l’Asia occidentale e l’Africa nord-orientale", "old_world": "il Vecchio Mondo, con una lunga storia di coltivazione in Asia ed Europa", "east_asia": "l’Asia orientale", "europe_west_asia": "l’Europa e l’Asia occidentale", "mediterranean": "la regione mediterranea", "asia_europe": "l’Asia e l’Europa", "unknown": "una lunga storia di coltivazione che dipende dalla varietà"},
        "flavor": {"mild_mustard": "fresco e delicatamente senapato", "citrus_herbal": "vivace, agrumato ed erbaceo", "mild_cabbage": "delicato, simile al cavolo, con una leggera dolcezza", "peppery": "pulito e pepato", "radish_peppery": "croccante e tipicamente pepato come il ravanello", "clean_radish": "fresco e moderatamente pepato come il ravanello", "mild_turnip": "delicato, fresco e leggermente simile ai cavoli", "peppery_nutty": "pepato con una leggera nota di nocciola", "bitter_mustard": "piacevolmente amarognolo con nota di senape", "mustard_spicy": "senapato e piccante", "unknown": "fresco e concentrato"},
        "color": {"fine_green": "foglie verdi fini e frastagliate", "soft_green": "germogli verdi delicati", "green_purple": "germogli verdi che possono mostrare toni viola", "bright_green": "germogli verde brillante", "green_colored_stem": "foglie verdi con steli talvolta colorati", "pink_green": "foglie verdi con steli rosa-viola vivaci", "fresh_green": "germogli verdi freschi", "unknown": "giovani germogli verdi"},
        "relatives": {"brassica": "cavolo, rapa e senape", "carrot_parsley": "carota e prezzemolo", "cabbage_broccoli": "cavolo, broccoli e kale", "mustard_radish": "senape, ravanello e altre Brassicaceae", "unknown": "altre piante commestibili dello stesso gruppo botanico"},
    },
    "pt": {
        "family": {"brassicaceae": "à família das Brassicaceae", "apiaceae": "à família das Apiaceae", "unknown": "a uma família botânica definida pela variedade"},
        "origin": {"japan": "o Japão e o Leste Asiático", "med_west_asia": "o Mediterrâneo e a Ásia Ocidental", "europe": "a Europa", "west_asia_africa": "a Ásia Ocidental e o nordeste de África", "old_world": "o Velho Mundo, com longa história de cultivo na Ásia e na Europa", "east_asia": "o Leste Asiático", "europe_west_asia": "a Europa e a Ásia Ocidental", "mediterranean": "a região mediterrânica", "asia_europe": "a Ásia e a Europa", "unknown": "uma longa história de cultivo que depende da variedade"},
        "flavor": {"mild_mustard": "fresco e suavemente mostardado", "citrus_herbal": "vivo, cítrico e herbal", "mild_cabbage": "suave, lembrando couve, com leve doçura", "peppery": "limpo e apimentado", "radish_peppery": "crocante e tipicamente picante como rabanete", "clean_radish": "fresco e moderadamente picante como rabanete", "mild_turnip": "suave, fresco e levemente semelhante a couve", "peppery_nutty": "apimentado com leve nota de noz", "bitter_mustard": "agradavelmente amargo com nota de mostarda", "mustard_spicy": "mostardado e picante", "unknown": "fresco e concentrado"},
        "color": {"fine_green": "folhas verdes finas e recortadas", "soft_green": "rebentos verdes delicados", "green_purple": "rebentos verdes que podem mostrar tons roxos", "bright_green": "rebentos verde-vivo", "green_colored_stem": "folhas verdes com caules por vezes coloridos", "pink_green": "folhas verdes com caules rosa-roxo vivos", "fresh_green": "rebentos verdes frescos", "unknown": "rebentos verdes jovens"},
        "relatives": {"brassica": "couve, nabo e mostarda", "carrot_parsley": "cenoura e salsa", "cabbage_broccoli": "couve, brócolos e kale", "mustard_radish": "mostarda, rabanete e outras Brassicaceae", "unknown": "outras plantas comestíveis do mesmo grupo botânico"},
    },
    "pl": {
        "family": {"brassicaceae": "do rodziny kapustowatych (Brassicaceae)", "apiaceae": "do rodziny selerowatych (Apiaceae)", "unknown": "do rodziny botanicznej zależnej od odmiany"},
        "origin": {"japan": "Japonię i Azję Wschodnią", "med_west_asia": "rejon Morza Śródziemnego i Azję Zachodnią", "europe": "Europę", "west_asia_africa": "Azję Zachodnią i północno-wschodnią Afrykę", "old_world": "Stary Świat i długą historię uprawy w Azji oraz Europie", "east_asia": "Azję Wschodnią", "europe_west_asia": "Europę i Azję Zachodnią", "mediterranean": "region śródziemnomorski", "asia_europe": "Azję i Europę", "unknown": "długą historię uprawy zależną od odmiany"},
        "flavor": {"mild_mustard": "świeży i łagodnie musztardowy", "citrus_herbal": "wyrazisty, cytrusowy i ziołowy", "mild_cabbage": "łagodnie kapuściany z nutą słodyczy", "peppery": "czysty i pieprzny", "radish_peppery": "chrupiący i wyraźnie pieprzny jak rzodkiewka", "clean_radish": "świeży i umiarkowanie pikantny jak rzodkiew", "mild_turnip": "łagodny, świeży i lekko kapuściany", "peppery_nutty": "pieprzny z lekką nutą orzechową", "bitter_mustard": "przyjemnie gorzkawy z nutą musztardy", "mustard_spicy": "musztardowy i pikantny", "unknown": "świeży i skoncentrowany"},
        "color": {"fine_green": "drobne, postrzępione zielone liście", "soft_green": "delikatne zielone pędy", "green_purple": "zielone pędy z możliwymi fioletowymi tonami", "bright_green": "jasnozielone pędy", "green_colored_stem": "zielone liście z czasem barwnymi łodyżkami", "pink_green": "zielone liście z intensywnie różowo-fioletowymi łodyżkami", "fresh_green": "świeże zielone pędy", "unknown": "młode zielone pędy"},
        "relatives": {"brassica": "kapusta, rzepa i gorczyca", "carrot_parsley": "marchew i pietruszka", "cabbage_broccoli": "kapusta, brokuł i jarmuż", "mustard_radish": "gorczyca, rzodkiewka i inne kapustowate", "unknown": "inne jadalne rośliny z tej samej grupy botanicznej"},
    },
    "zh": {
        "family": {"brassicaceae": "十字花科（Brassicaceae）", "apiaceae": "伞形科（Apiaceae）", "unknown": "由具体品种决定的植物科属"},
        "origin": {"japan": "日本和东亚", "med_west_asia": "地中海地区和西亚", "europe": "欧洲", "west_asia_africa": "西亚和非洲东北部", "old_world": "旧大陆，并在亚洲和欧洲拥有悠久栽培历史", "east_asia": "东亚", "europe_west_asia": "欧洲和西亚", "mediterranean": "地中海地区", "asia_europe": "亚洲和欧洲", "unknown": "因品种而异的悠久栽培历史"},
        "flavor": {"mild_mustard": "清新且带温和芥末味", "citrus_herbal": "明亮的柑橘与草本风味", "mild_cabbage": "温和的甘蓝味并带一点甜味", "peppery": "清爽而有胡椒辛香", "radish_peppery": "爽脆并带典型萝卜辛香", "clean_radish": "清新、适度的萝卜辛香", "mild_turnip": "温和清新并带轻微甘蓝风味", "peppery_nutty": "胡椒辛香并带淡淡坚果味", "bitter_mustard": "宜人的微苦与芥末风味", "mustard_spicy": "明显的芥末辛香", "unknown": "清新而浓郁"},
        "color": {"fine_green": "细致、羽状的绿色叶片", "soft_green": "柔嫩的绿色幼苗", "green_purple": "可能带紫色调的绿色幼苗", "bright_green": "鲜绿色幼苗", "green_colored_stem": "绿色叶片和可能带颜色的茎", "pink_green": "绿色叶片配鲜艳粉紫色茎", "fresh_green": "清新的绿色幼苗", "unknown": "年轻的绿色幼苗"},
        "relatives": {"brassica": "甘蓝、芜菁和芥菜", "carrot_parsley": "胡萝卜和欧芹", "cabbage_broccoli": "甘蓝、西兰花和羽衣甘蓝", "mustard_radish": "芥菜、萝卜以及其他十字花科植物", "unknown": "同一植物类群中的其他食用植物"},
    },
}


TEMPLATES = {
    "en": [
        "Botanically, {name} belongs to {family}.",
        "The botanical name associated with this crop is {species}.",
        "The cultivation history of {name} is closely connected with {origin}.",
        "At the microgreen stage, {name} already shows the character of the mature plant, but in a much smaller form.",
        "Its characteristic flavour at this stage is {flavor}.",
        "A typical tray develops {color}.",
        "Botanical relatives include {relatives}.",
        "The first leaf-like parts you see are cotyledons — the seed leaves that feed the young seedling at the start.",
        "If the crop grows a little longer, the first true leaves begin to appear above the cotyledons.",
        "Microgreens are harvested long before the plant reaches its full adult size.",
        "After germination, light triggers chlorophyll formation and the shoots become greener.",
        "Seed coats can sometimes remain on the tips of young shoots for a while after germination.",
        "The edible harvest is the tender shoot above the growing medium; the roots normally stay behind.",
        "Young {name} is usually served fresh so its delicate texture and aroma remain noticeable.",
        "A small amount can add a surprisingly clear flavour accent to a finished dish.",
        "Dense sowing makes a compact canopy, which is one reason microgreens look so different from mature plants.",
        "Colour and stem tone can become more pronounced as the seedlings receive light.",
        "The same species can look dramatically different as a microgreen and as a fully grown vegetable or herb.",
        "Because the crop is cut young, the whole growing cycle is measured in days rather than months.",
        "Microgreens turn the very first stage of a plant’s life into a ready-to-use culinary ingredient.",
    ],
    "ru": [
        "С ботанической точки зрения {name} относится к {family}.",
        "Ботаническое название этой культуры — {species}.",
        "История выращивания {name} тесно связана с регионом: {origin}.",
        "Уже на стадии микрозелени {name} показывает характер взрослого растения, только в миниатюре.",
        "Характерный вкус на этой стадии — {flavor}.",
        "Типичный лоток формирует {color}.",
        "Среди ботанических родственников — {relatives}.",
        "Первые листочки, которые видны после всходов, — это семядоли: они помогают молодому ростку на старте.",
        "Если дать культуре расти чуть дольше, над семядолями начинают появляться первые настоящие листья.",
        "Микрозелень срезают задолго до того, как растение достигнет взрослого размера.",
        "После прорастания свет запускает образование хлорофилла, и побеги становятся зеленее.",
        "После прорастания оболочка семени иногда ещё некоторое время остаётся на кончиках молодых побегов.",
        "В пищу обычно срезают нежную надземную часть, а корни остаются в субстрате.",
        "Молодую зелень {name} чаще используют свежей, чтобы сохранить нежную текстуру и аромат.",
        "Даже небольшая порция может дать готовому блюду заметный вкусовой акцент.",
        "Плотный посев образует сплошной зелёный ковёр — поэтому микрозелень так не похожа на взрослое растение.",
        "Окраска листьев и стеблей может становиться ярче по мере того, как всходы получают свет.",
        "Один и тот же вид может выглядеть совсем по-разному как микрозелень и как взрослая овощная или пряная культура.",
        "Поскольку урожай срезают молодым, полный цикл микрозелени измеряется днями, а не месяцами.",
        "Микрозелень превращает самый ранний этап жизни растения в готовый к использованию кулинарный продукт.",
    ],
    "de": [
        "Botanisch gehört {name} {family}.",
        "Der botanische Name dieser Kultur ist {species}.",
        "Die Anbaugeschichte von {name} ist eng verbunden mit {origin}.",
        "Schon als Microgreen zeigt {name} den Charakter der ausgewachsenen Pflanze – nur im Kleinformat.",
        "Der typische Geschmack in diesem Stadium ist {flavor}.",
        "Eine typische Schale entwickelt {color}.",
        "Botanische Verwandte sind unter anderem {relatives}.",
        "Die ersten blattähnlichen Teile sind Keimblätter; sie versorgen den jungen Sämling am Anfang.",
        "Wächst die Kultur etwas länger, erscheinen über den Keimblättern die ersten echten Blätter.",
        "Microgreens werden lange geerntet, bevor die Pflanze ihre ausgewachsene Größe erreicht.",
        "Nach der Keimung fördert Licht die Chlorophyllbildung und die Triebe werden grüner.",
        "Samenschalen können nach der Keimung noch eine Zeit lang an den Spitzen junger Triebe haften.",
        "Geerntet wird der zarte Trieb über dem Substrat; die Wurzeln bleiben normalerweise zurück.",
        "Junge {name} werden meist frisch verwendet, damit Textur und Aroma erhalten bleiben.",
        "Schon eine kleine Menge kann einem fertigen Gericht einen deutlichen Geschmacksakzent geben.",
        "Dichte Aussaat bildet einen kompakten Pflanzenteppich – deshalb sehen Microgreens ganz anders aus als ausgewachsene Pflanzen.",
        "Farbe und Stieltöne können mit zunehmendem Licht kräftiger werden.",
        "Dieselbe Art kann als Microgreen völlig anders aussehen als als ausgewachsenes Gemüse oder Kraut.",
        "Weil so jung geerntet wird, misst man den Wachstumszyklus in Tagen statt in Monaten.",
        "Microgreens machen aus der allerersten Lebensphase einer Pflanze eine direkt nutzbare Küchenzutat.",
    ],
    "fr": [
        "Botaniquement, {name} appartient {family}.",
        "Le nom botanique associé à cette culture est {species}.",
        "L’histoire de la culture de {name} est étroitement liée à {origin}.",
        "Au stade de micropousse, {name} montre déjà le caractère de la plante adulte, en miniature.",
        "Sa saveur caractéristique à ce stade est {flavor}.",
        "Un plateau typique développe {color}.",
        "Parmi ses proches parents botaniques figurent {relatives}.",
        "Les premières parties ressemblant à des feuilles sont les cotylédons, les feuilles de réserve de la jeune plantule.",
        "Si la culture pousse un peu plus longtemps, les premières vraies feuilles apparaissent au-dessus des cotylédons.",
        "Les micropousses sont récoltées bien avant que la plante n’atteigne sa taille adulte.",
        "Après la germination, la lumière stimule la formation de chlorophylle et les pousses verdissent.",
        "Après la germination, l’enveloppe de la graine peut rester un moment au bout des jeunes pousses.",
        "On récolte la pousse tendre au-dessus du substrat; les racines restent généralement en place.",
        "Les jeunes pousses de {name} sont le plus souvent consommées fraîches pour préserver texture et arôme.",
        "Une petite quantité peut apporter un accent gustatif très net à un plat terminé.",
        "Un semis dense forme un tapis compact, ce qui explique l’aspect très différent des micropousses et des plantes adultes.",
        "La couleur des feuilles et des tiges peut s’intensifier à mesure que les plantules reçoivent de la lumière.",
        "Une même espèce peut avoir une apparence radicalement différente en micropousse et à maturité.",
        "Comme la récolte est très jeune, le cycle de culture se compte en jours plutôt qu’en mois.",
        "Les micropousses transforment le tout premier stade de vie d’une plante en ingrédient culinaire prêt à l’emploi.",
    ],
    "es": [
        "Botánicamente, {name} pertenece {family}.",
        "El nombre botánico asociado a este cultivo es {species}.",
        "La historia de cultivo de {name} está estrechamente relacionada con {origin}.",
        "En fase de microbrote, {name} ya muestra el carácter de la planta adulta, pero en miniatura.",
        "Su sabor característico en esta etapa es {flavor}.",
        "Una bandeja típica desarrolla {color}.",
        "Entre sus parientes botánicos se encuentran {relatives}.",
        "Las primeras partes parecidas a hojas son los cotiledones, las hojas de reserva de la plántula.",
        "Si se deja crecer un poco más, empiezan a aparecer las primeras hojas verdaderas sobre los cotiledones.",
        "Los microbrotes se cosechan mucho antes de que la planta alcance su tamaño adulto.",
        "Tras la germinación, la luz activa la formación de clorofila y los brotes se vuelven más verdes.",
        "La cubierta de la semilla puede permanecer un tiempo en la punta de los brotes jóvenes después de germinar.",
        "Se cosecha el brote tierno sobre el sustrato; las raíces normalmente se quedan en él.",
        "El {name} joven suele servirse fresco para conservar su textura y aroma delicados.",
        "Una pequeña cantidad puede aportar un acento de sabor sorprendentemente claro a un plato terminado.",
        "La siembra densa forma una cubierta compacta y por eso los microbrotes se ven tan distintos de las plantas adultas.",
        "El color de hojas y tallos puede intensificarse a medida que las plántulas reciben luz.",
        "La misma especie puede verse completamente distinta como microbrote y como verdura o hierba adulta.",
        "Como se corta muy joven, el ciclo completo se mide en días y no en meses.",
        "Los microbrotes convierten la primera etapa de vida de una planta en un ingrediente culinario listo para usar.",
    ],
    "it": [
        "Botanicamente, {name} appartiene {family}.",
        "Il nome botanico associato a questa coltura è {species}.",
        "La storia della coltivazione di {name} è strettamente legata a {origin}.",
        "Nella fase di microgreen, {name} mostra già il carattere della pianta adulta, ma in miniatura.",
        "Il sapore caratteristico in questa fase è {flavor}.",
        "Un vassoio tipico sviluppa {color}.",
        "Tra i parenti botanici troviamo {relatives}.",
        "Le prime parti simili a foglie sono i cotiledoni, le foglie di riserva della giovane piantina.",
        "Se la coltura cresce un po’ più a lungo, sopra i cotiledoni iniziano a comparire le prime foglie vere.",
        "I microgreens vengono raccolti molto prima che la pianta raggiunga la dimensione adulta.",
        "Dopo la germinazione, la luce stimola la formazione di clorofilla e i germogli diventano più verdi.",
        "Il tegumento del seme può rimanere per un po’ sulla punta dei giovani germogli dopo la germinazione.",
        "Si raccoglie il germoglio tenero sopra il substrato; le radici normalmente restano nel vassoio.",
        "Il giovane {name} si usa spesso fresco per mantenere riconoscibili consistenza e aroma delicati.",
        "Anche una piccola quantità può dare un accento di gusto molto evidente a un piatto finito.",
        "La semina fitta crea una copertura compatta: per questo i microgreens sembrano così diversi dalle piante adulte.",
        "Il colore di foglie e steli può diventare più intenso man mano che le piantine ricevono luce.",
        "La stessa specie può apparire completamente diversa come microgreen e come ortaggio o erba adulta.",
        "Poiché il raccolto avviene molto presto, il ciclo completo si misura in giorni e non in mesi.",
        "I microgreens trasformano la primissima fase di vita di una pianta in un ingrediente pronto per la cucina.",
    ],
    "pt": [
        "Botanicamente, {name} pertence {family}.",
        "O nome botânico associado a esta cultura é {species}.",
        "A história de cultivo de {name} está fortemente ligada a {origin}.",
        "Na fase de microverde, {name} já mostra o caráter da planta adulta, mas em miniatura.",
        "O sabor característico nesta fase é {flavor}.",
        "Um tabuleiro típico desenvolve {color}.",
        "Entre os parentes botânicos estão {relatives}.",
        "As primeiras partes parecidas com folhas são os cotilédones, as folhas de reserva da jovem plântula.",
        "Se crescer um pouco mais, começam a surgir as primeiras folhas verdadeiras acima dos cotilédones.",
        "Os microverdes são colhidos muito antes de a planta atingir o tamanho adulto.",
        "Depois da germinação, a luz estimula a formação de clorofila e os rebentos ficam mais verdes.",
        "A casca da semente pode permanecer algum tempo na ponta dos rebentos jovens após a germinação.",
        "Colhe-se o rebento tenro acima do substrato; as raízes normalmente ficam no tabuleiro.",
        "O jovem {name} costuma ser servido fresco para preservar a textura e o aroma delicados.",
        "Uma pequena quantidade pode dar um acento de sabor surpreendentemente claro a um prato pronto.",
        "A sementeira densa cria uma cobertura compacta, razão pela qual os microverdes parecem tão diferentes das plantas adultas.",
        "A cor das folhas e dos caules pode intensificar-se à medida que as plântulas recebem luz.",
        "A mesma espécie pode parecer completamente diferente como microverde e como hortaliça ou erva adulta.",
        "Como a colheita é muito jovem, o ciclo completo mede-se em dias e não em meses.",
        "Os microverdes transformam a primeira fase de vida de uma planta num ingrediente culinário pronto a usar.",
    ],
    "pl": [
        "Botanicznie {name} należy {family}.",
        "Nazwa botaniczna związana z tą uprawą to {species}.",
        "Historia uprawy {name} jest silnie związana z regionem: {origin}.",
        "Już jako mikrolistki {name} pokazuje charakter dorosłej rośliny, tylko w miniaturze.",
        "Charakterystyczny smak na tym etapie jest {flavor}.",
        "Typowa tacka tworzy {color}.",
        "Do botanicznych krewniaków należą {relatives}.",
        "Pierwsze części podobne do liści to liścienie, czyli liście zapasowe młodej siewki.",
        "Gdy roślina rośnie trochę dłużej, nad liścieniami pojawiają się pierwsze liście właściwe.",
        "Mikrolistki zbiera się długo przed osiągnięciem przez roślinę dorosłego rozmiaru.",
        "Po kiełkowaniu światło uruchamia tworzenie chlorofilu i pędy stają się bardziej zielone.",
        "Łupina nasienna może przez pewien czas pozostawać na końcach młodych pędów po kiełkowaniu.",
        "Zbiera się delikatny pęd nad podłożem; korzenie zwykle pozostają w tacy.",
        "Młode {name} najczęściej podaje się świeże, aby zachować delikatną teksturę i aromat.",
        "Niewielka ilość może nadać gotowemu daniu zaskakująco wyraźny akcent smakowy.",
        "Gęsty siew tworzy zwartą warstwę zieleni, dlatego mikrolistki tak różnią się wyglądem od dorosłych roślin.",
        "Kolor liści i łodyg może stawać się intensywniejszy wraz z dostępem do światła.",
        "Ten sam gatunek może wyglądać zupełnie inaczej jako mikrolistki i jako dorosłe warzywo lub zioło.",
        "Ponieważ zbiór następuje bardzo wcześnie, cały cykl liczy się w dniach, a nie miesiącach.",
        "Mikrolistki zamieniają najwcześniejszy etap życia rośliny w gotowy do użycia składnik kulinarny.",
    ],
    "zh": [
        "从植物分类上看，{name}属于{family}。",
        "这种作物对应的植物学名称是 {species}。",
        "{name} 的栽培历史与{origin}密切相关。",
        "在微型蔬菜阶段，{name} 已经能表现出成熟植株的特征，只是体型更小。",
        "这一阶段最有代表性的风味是{flavor}。",
        "一盘典型幼苗会形成{color}。",
        "它的植物学近亲包括{relatives}。",
        "发芽后最先看到的“叶子”其实是子叶，它们为幼苗早期生长提供储备。",
        "如果再多生长一段时间，子叶上方会开始出现第一片真叶。",
        "微型蔬菜在植株达到完全成熟大小之前很早就会被采收。",
        "发芽后，光照会促进叶绿素形成，幼苗也会越来越绿。",
        "种皮有时会在发芽后继续停留在幼苗顶端一段时间。",
        "食用部分通常是基质上方的嫩芽，根系则留在栽培基质中。",
        "年轻的{name}通常以新鲜状态食用，以保留细嫩口感和香气。",
        "即使只用少量，也能给成品菜肴带来很清晰的风味点缀。",
        "密集播种会形成紧凑的绿色冠层，这也是微型蔬菜与成熟植株外观差异很大的原因。",
        "随着幼苗获得光照，叶片和茎的颜色可能会变得更鲜明。",
        "同一种植物在微型蔬菜阶段和完全成熟阶段，外观可能完全不同。",
        "因为采收非常早，整个生长周期通常以天而不是月来计算。",
        "微型蔬菜把植物生命最早期的阶段直接变成了可用于烹饪的食材。",
    ],
}


def _profile_values(key: str | None, lang: str) -> dict[str, str]:
    profile = PROFILES.get(key or "", {})
    words = WORDS[lang]
    return {
        "family": words["family"].get(profile.get("family"), words["family"]["unknown"]),
        "species": profile.get("species") or "—",
        "origin": words["origin"].get(profile.get("origin"), words["origin"]["unknown"]),
        "flavor": words["flavor"].get(profile.get("flavor"), words["flavor"]["unknown"]),
        "color": words["color"].get(profile.get("color"), words["color"]["unknown"]),
        "relatives": words["relatives"].get(profile.get("relatives"), words["relatives"]["unknown"]),
    }


def facts_for_plant(plant: Plant, lang: str) -> list[str]:
    key = _plant_key(plant)
    values = _profile_values(key, lang)
    values["name"] = _localized_name(plant, lang)
    return [template.format(**values) for template in TEMPLATES[lang]][:TARGET_FACTS]


async def ensure_plant_facts() -> int:
    """Ensure every plant has a reusable pool of localized watering facts.

    Existing operator-written facts are preserved. Missing languages are filled,
    and short lists are extended to TARGET_FACTS without replacing custom text.
    """
    changed = 0
    async with SessionLocal() as session:
        plants = (await session.execute(select(Plant))).scalars().all()
        for plant in plants:
            current = dict(plant.facts or {})
            modified = False
            for lang in LANGS:
                existing = [str(item).strip() for item in (current.get(lang) or []) if str(item).strip()]
                generated = facts_for_plant(plant, lang)
                merged = list(existing)
                for fact in generated:
                    if fact not in merged and len(merged) < TARGET_FACTS:
                        merged.append(fact)
                if merged != (current.get(lang) or []):
                    current[lang] = merged[:40]
                    modified = True
            if modified:
                plant.facts = current
                plant.updated_at = _now_naive()
                changed += 1
        if changed:
            await session.commit()
    if changed:
        print(f"[plants] multilingual fact pools populated for {changed} plant(s)")
    return changed
