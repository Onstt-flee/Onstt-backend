"""Natural, deterministic acceptable examples for pilot v0.1."""

from __future__ import annotations


def add_acceptable_natural(builder, lexicon: dict) -> None:
    """Add 135 grammar-acceptable records without random lexical cross-products."""
    places = lexicon["places"]
    objects = lexicon["objects"]

    for place in places[:9]:
        builder.acceptable("acceptable_destination", f"来月は{place}に行きます。", None, "목적지에는 に를 사용할 수 있습니다.")

    action_pairs = [
        ("駅", "切符"), ("スーパー", "傘"), ("図書館", "本"),
        ("カフェ", "コーヒー"), ("病院", "薬"), ("学校", "ノート"),
        ("レストラン", "昼ご飯"), ("コンビニ", "新聞"), ("ホテル", "水"),
    ]
    for place, obj in action_pairs:
        builder.acceptable("acceptable_action_location", f"{place}で{obj}を買いました。", None, "동작이 일어난 장소에는 で가 적절합니다.")

    for place in ["公園", "商店街", "橋", "道", "駅前", "海岸", "森", "町", "川沿い"]:
        builder.acceptable("acceptable_route", f"朝、{place}をゆっくり歩きました。", None, "이동한 경로를 나타내는 を가 적절합니다.")

    possession_pairs = [
        ("友達", "本"), ("先生", "傘"), ("家族", "鞄"),
        ("隣人", "スマホ"), ("店員", "名札"), ("医者", "筆記用具"),
        ("学生", "ノート"), ("観光客", "カメラ"), ("職人", "時計"),
    ]
    for person, obj in possession_pairs:
        builder.acceptable("acceptable_possession", f"これは{person}の{obj}です。", None, "명사 사이의 소유·관계에는 の가 적절합니다.")

    for obj in ["名前", "住所", "電話番号", "予定", "答え", "感想", "理由", "日付", "番号"]:
        builder.acceptable("acceptable_te_request", f"こちらの用紙に{obj}を書いてください。", None, "書く의 て형과 요청 표현이 올바르게 연결됩니다.")

    past_negative = [
        "その本は厚くなかったです。", "その傘は高くなかったです。", "その鞄は重くなかったです。",
        "そのスマホは安くなかったです。", "そのコーヒーは熱くなかったです。", "その店の筆記用具は多くなかったです。",
        "そのノートは大きくなかったです。", "その服は新しくなかったです。", "その時計は古くなかったです。",
    ]
    for text in past_negative:
        builder.acceptable("acceptable_i_past_negative", text, None, "형용사의 과거 부정형이 적절합니다.")

    na_modifier_pairs = [
        ("静か", "町"), ("きれい", "部屋"), ("有名", "店"),
        ("広大", "公園"), ("安全", "道"), ("便利", "ホテル"),
        ("立派", "学校"), ("特別", "場所"), ("おしゃれ", "カフェ"),
    ]
    for adjective, noun in na_modifier_pairs:
        builder.acceptable("acceptable_na_modifier", f"{adjective}な{noun}ですね。", None, "な형용사가 な를 사용해 명사를 수식합니다.")

    i_modifier_pairs = [
        ("厚い", "本"), ("大きい", "傘"), ("軽い", "鞄"),
        ("新しい", "スマホ"), ("温かい", "コーヒー"), ("使いやすい", "筆記用具"),
        ("薄い", "ノート"), ("安い", "服"), ("高い", "時計"),
    ]
    for adjective, noun in i_modifier_pairs:
        builder.acceptable("acceptable_i_modifier", f"{adjective}{noun}を選びました。", None, "い형용사가 그대로 명사를 수식합니다.")

    for place in places[:9]:
        builder.acceptable("acceptable_embedded_plain", f"来週は{place}に行くと思います。", None, "と思います 앞의 보통형이 적절합니다.")
    for obj in objects[:9]:
        builder.acceptable("acceptable_colloquial_ellipsis", f"{obj}、もう持ってきたよ。", "친구에게 준비물을 가져왔다고 말합니다.", "회화에서 목적격 조사를 생략할 수 있습니다.")

    for text in [
        "今は何してる？", "そこで何してる？", "今日は何してる？", "先生、何してる？",
        "駅で何してる？", "一人で何してる？", "朝から何してる？", "まだ何してる？", "外で何してる？",
    ]:
        builder.acceptable("acceptable_contraction", text, "친한 사이의 일상 대화입니다.", "している의 회화 축약형 してる를 허용합니다.")

    fillers = ["あのう", "ええと", "そうですね", "ええ", "あの", "その", "うーん", "まあ", "えっと"]
    for filler, place in zip(fillers, places):
        builder.acceptable("acceptable_filler", f"{filler}、今夜は{place}に行きます。", None, "완성된 문장 속 필러를 문법 오류로 보지 않습니다.")

    short_answers = [
        ("まだ終えていません。", "숙제를 끝냈는지 물었습니다."),
        ("図書館です。", "어디에서 공부하는지 물었습니다."),
        ("三時です。", "몇 시에 만나는지 물었습니다."),
        ("友達です。", "함께 온 사람이 누구인지 물었습니다."),
        ("明日です。", "출발일이 언제인지 물었습니다."),
        ("はい、お願いします。", "도움을 줄지 제안받았습니다."),
        ("二つです。", "몇 개 필요한지 물었습니다."),
        ("電車です。", "무엇을 타고 왔는지 물었습니다."),
        ("大丈夫です。", "도움이 필요한지 물었습니다."),
    ]
    for text, context in short_answers:
        builder.acceptable("acceptable_short_answer", text, context, "주어진 질문에 대한 짧은 응답으로 성립합니다.")

    style_switches = [
        "先週は公園に行きました。それから写真を撮った。",
        "先週は駅に行きました。それから切符を買った。",
        "先週はスーパーに行きました。それから野菜を買った。",
        "先週は図書館に行きました。それから本を借りた。",
        "先週はカフェに行きました。それからコーヒーを飲んだ。",
        "先週は病院に行きました。それから薬をもらった。",
        "先週は学校に行きました。それから授業を受けた。",
        "先週はレストランに行きました。それから昼ご飯を食べた。",
        "先週はコンビニに行きました。それから新聞を買った。",
    ]
    for text in style_switches:
        builder.acceptable("acceptable_style_switch", text, "친구에게 지난 일을 말하며 문체 통일 요구는 없습니다.", "각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다.")
    for place in places[:9]:
        builder.acceptable("acceptable_conditional_potential", f"この道なら、{place}まで歩いて行けます。", None, "なら와 가능형 行けます의 연결이 적절합니다.")
