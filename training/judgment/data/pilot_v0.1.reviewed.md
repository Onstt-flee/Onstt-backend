# 일본어 판단 LoRA 파일럿 v0.1 — 검수용 보기

상태: 300문항 모두 `provisional`. 이 문서는 검수 보기이며 JSONL이 정답 원본입니다.
Qwen3-14B는 어휘·상황 후보만 제공했고 판단·교정·edit는 결정론적 템플릿으로 만들었습니다.
승인 전 학습에는 사용하지 않습니다. 개인 검수자 식별자는 기록하지 않습니다.

| ID | split | 수준 | 입력 | 문맥 | 판단안 | 교정안 | 오류 유형 | 근거 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JT-0001 | pilot_train | N5 | 来月は公園に行きます。 | — | acceptable | 来月は公園に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0002 | pilot_train | N5 | 来月は駅に行きます。 | — | acceptable | 来月は駅に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0003 | pilot_train | N4 | 来月はスーパーに行きます。 | — | acceptable | 来月はスーパーに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0004 | pilot_train | N5 | 来月は図書館に行きます。 | — | acceptable | 来月は図書館に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0005 | pilot_train | N5 | 来月はカフェに行きます。 | — | acceptable | 来月はカフェに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0006 | pilot_train | N4 | 来月は病院に行きます。 | — | acceptable | 来月は病院に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0007 | pilot_train | N5 | 来月は学校に行きます。 | — | acceptable | 来月は学校に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0008 | pilot_train | N5 | 来月はレストランに行きます。 | — | acceptable | 来月はレストランに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0009 | pilot_train | N4 | 来月はコンビニに行きます。 | — | acceptable | 来月はコンビニに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0010 | pilot_train | N5 | 駅で切符を買いました。 | — | acceptable | 駅で切符を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0011 | pilot_train | N5 | スーパーで傘を買いました。 | — | acceptable | スーパーで傘を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0012 | pilot_train | N5 | 図書館で本を買いました。 | — | acceptable | 図書館で本を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0013 | pilot_train | N4 | カフェでコーヒーを買いました。 | — | acceptable | カフェでコーヒーを買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0014 | pilot_train | N5 | 病院で薬を買いました。 | — | acceptable | 病院で薬を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0015 | pilot_train | N5 | 学校でノートを買いました。 | — | acceptable | 学校でノートを買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0016 | pilot_train | N4 | レストランで昼ご飯を買いました。 | — | acceptable | レストランで昼ご飯を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0017 | pilot_train | N5 | コンビニで新聞を買いました。 | — | acceptable | コンビニで新聞を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0018 | pilot_train | N5 | ホテルで水を買いました。 | — | acceptable | ホテルで水を買いました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0019 | pilot_dev | N4 | 朝、公園をゆっくり歩きました。 | — | acceptable | 朝、公園をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0020 | pilot_dev | N5 | 朝、商店街をゆっくり歩きました。 | — | acceptable | 朝、商店街をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0021 | pilot_dev | N5 | 朝、橋をゆっくり歩きました。 | — | acceptable | 朝、橋をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0022 | pilot_dev | N5 | 朝、道をゆっくり歩きました。 | — | acceptable | 朝、道をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0023 | pilot_dev | N4 | 朝、駅前をゆっくり歩きました。 | — | acceptable | 朝、駅前をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0024 | pilot_dev | N5 | 朝、海岸をゆっくり歩きました。 | — | acceptable | 朝、海岸をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0025 | pilot_dev | N5 | 朝、森をゆっくり歩きました。 | — | acceptable | 朝、森をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0026 | pilot_dev | N4 | 朝、町をゆっくり歩きました。 | — | acceptable | 朝、町をゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0027 | pilot_dev | N5 | 朝、川沿いをゆっくり歩きました。 | — | acceptable | 朝、川沿いをゆっくり歩きました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0028 | pilot_train | N5 | これは友達の本です。 | — | acceptable | これは友達の本です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0029 | pilot_train | N4 | これは先生の傘です。 | — | acceptable | これは先生の傘です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0030 | pilot_train | N5 | これは家族の鞄です。 | — | acceptable | これは家族の鞄です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0031 | pilot_train | N5 | これは隣人のスマホです。 | — | acceptable | これは隣人のスマホです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0032 | pilot_train | N5 | これは店員の名札です。 | — | acceptable | これは店員の名札です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0033 | pilot_train | N4 | これは医者の筆記用具です。 | — | acceptable | これは医者の筆記用具です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0034 | pilot_train | N5 | これは学生のノートです。 | — | acceptable | これは学生のノートです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0035 | pilot_train | N5 | これは観光客のカメラです。 | — | acceptable | これは観光客のカメラです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0036 | pilot_train | N4 | これは職人の時計です。 | — | acceptable | これは職人の時計です。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0037 | pilot_train | N5 | こちらの用紙に名前を書いてください。 | — | acceptable | こちらの用紙に名前を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0038 | pilot_train | N5 | こちらの用紙に住所を書いてください。 | — | acceptable | こちらの用紙に住所を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0039 | pilot_train | N4 | こちらの用紙に電話番号を書いてください。 | — | acceptable | こちらの用紙に電話番号を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0040 | pilot_train | N5 | こちらの用紙に予定を書いてください。 | — | acceptable | こちらの用紙に予定を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0041 | pilot_train | N5 | こちらの用紙に答えを書いてください。 | — | acceptable | こちらの用紙に答えを書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0042 | pilot_train | N5 | こちらの用紙に感想を書いてください。 | — | acceptable | こちらの用紙に感想を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0043 | pilot_train | N4 | こちらの用紙に理由を書いてください。 | — | acceptable | こちらの用紙に理由を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0044 | pilot_train | N5 | こちらの用紙に日付を書いてください。 | — | acceptable | こちらの用紙に日付を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0045 | pilot_train | N5 | こちらの用紙に番号を書いてください。 | — | acceptable | こちらの用紙に番号を書いてください。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0046 | pilot_train | N4 | その本は厚くなかったです。 | — | acceptable | その本は厚くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0047 | pilot_train | N5 | その傘は高くなかったです。 | — | acceptable | その傘は高くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0048 | pilot_train | N5 | その鞄は重くなかったです。 | — | acceptable | その鞄は重くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0049 | pilot_train | N4 | そのスマホは安くなかったです。 | — | acceptable | そのスマホは安くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0050 | pilot_train | N5 | そのコーヒーは熱くなかったです。 | — | acceptable | そのコーヒーは熱くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0051 | pilot_train | N5 | その店の筆記用具は多くなかったです。 | — | acceptable | その店の筆記用具は多くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0052 | pilot_train | N5 | そのノートは大きくなかったです。 | — | acceptable | そのノートは大きくなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0053 | pilot_train | N4 | その服は新しくなかったです。 | — | acceptable | その服は新しくなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0054 | pilot_train | N5 | その時計は古くなかったです。 | — | acceptable | その時計は古くなかったです。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0055 | pilot_train | N5 | 静かな町ですね。 | — | acceptable | 静かな町ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0056 | pilot_train | N4 | きれいな部屋ですね。 | — | acceptable | きれいな部屋ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0057 | pilot_train | N5 | 有名な店ですね。 | — | acceptable | 有名な店ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0058 | pilot_train | N5 | 広大な公園ですね。 | — | acceptable | 広大な公園ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0059 | pilot_train | N4 | 安全な道ですね。 | — | acceptable | 安全な道ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0060 | pilot_train | N5 | 便利なホテルですね。 | — | acceptable | 便利なホテルですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0061 | pilot_train | N5 | 立派な学校ですね。 | — | acceptable | 立派な学校ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0062 | pilot_train | N5 | 特別な場所ですね。 | — | acceptable | 特別な場所ですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0063 | pilot_train | N4 | おしゃれなカフェですね。 | — | acceptable | おしゃれなカフェですね。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0064 | pilot_train | N5 | 厚い本を選びました。 | — | acceptable | 厚い本を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0065 | pilot_train | N5 | 大きい傘を選びました。 | — | acceptable | 大きい傘を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0066 | pilot_train | N4 | 軽い鞄を選びました。 | — | acceptable | 軽い鞄を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0067 | pilot_train | N5 | 新しいスマホを選びました。 | — | acceptable | 新しいスマホを選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0068 | pilot_train | N5 | 温かいコーヒーを選びました。 | — | acceptable | 温かいコーヒーを選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0069 | pilot_train | N4 | 使いやすい筆記用具を選びました。 | — | acceptable | 使いやすい筆記用具を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0070 | pilot_train | N5 | 薄いノートを選びました。 | — | acceptable | 薄いノートを選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0071 | pilot_train | N5 | 安い服を選びました。 | — | acceptable | 安い服を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0072 | pilot_train | N5 | 高い時計を選びました。 | — | acceptable | 高い時計を選びました。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0073 | pilot_train | N4 | 来週は公園に行くと思います。 | — | acceptable | 来週は公園に行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0074 | pilot_train | N5 | 来週は駅に行くと思います。 | — | acceptable | 来週は駅に行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0075 | pilot_train | N5 | 来週はスーパーに行くと思います。 | — | acceptable | 来週はスーパーに行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0076 | pilot_train | N4 | 来週は図書館に行くと思います。 | — | acceptable | 来週は図書館に行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0077 | pilot_train | N5 | 来週はカフェに行くと思います。 | — | acceptable | 来週はカフェに行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0078 | pilot_train | N5 | 来週は病院に行くと思います。 | — | acceptable | 来週は病院に行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0079 | pilot_train | N4 | 来週は学校に行くと思います。 | — | acceptable | 来週は学校に行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0080 | pilot_train | N5 | 来週はレストランに行くと思います。 | — | acceptable | 来週はレストランに行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0081 | pilot_train | N5 | 来週はコンビニに行くと思います。 | — | acceptable | 来週はコンビニに行くと思います。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0082 | pilot_train | N5 | 本、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 本、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0083 | pilot_train | N4 | 傘、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 傘、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0084 | pilot_train | N5 | 鞄、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 鞄、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0085 | pilot_train | N5 | スマホ、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | スマホ、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0086 | pilot_train | N4 | コーヒー、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | コーヒー、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0087 | pilot_train | N5 | 筆記用具、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 筆記用具、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0088 | pilot_train | N5 | ノート、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | ノート、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0089 | pilot_train | N4 | 服、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 服、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0090 | pilot_train | N5 | 時計、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 時計、もう持ってきたよ。 | — | 조사가 생략되었으나 친밀한 일상 대화 문맥상 문법적으로 허용됩니다. | user_reviewed |
| JT-0091 | pilot_train | N5 | 今は何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 今は何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0092 | pilot_train | N5 | そこで何してる？ | 친한 사이의 일상 대화입니다. | acceptable | そこで何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0093 | pilot_train | N4 | 今日は何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 今日は何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0094 | pilot_train | N5 | 先生、何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 先生、何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0095 | pilot_train | N5 | 駅で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 駅で何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0096 | pilot_train | N4 | 一人で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 一人で何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0097 | pilot_train | N5 | 朝から何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 朝から何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0098 | pilot_train | N5 | まだ何してる？ | 친한 사이의 일상 대화입니다. | acceptable | まだ何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0099 | pilot_train | N4 | 外で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 外で何してる？ | — | 진행형의 'い' 생략은 구어체에서 허용되며 문법적 오류가 아닙니다. | user_reviewed |
| JT-0100 | pilot_dev | N5 | あのう、今夜は公園に行きます。 | — | acceptable | あのう、今夜は公園に行きます。 | — | 문법적 오류가 없습니다. 문두의 필러(あのう)는 오류가 아닙니다. | user_reviewed |
| JT-0101 | pilot_dev | N5 | ええと、今夜は駅に行きます。 | — | acceptable | ええと、今夜は駅に行きます。 | — | 문법적 오류가 없습니다. 문두의 필러(ええと)는 오류가 아닙니다. | user_reviewed |
| JT-0102 | pilot_dev | N5 | そうですね、今夜はスーパーに行きます。 | — | acceptable | そうですね、今夜はスーパーに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0103 | pilot_dev | N4 | ええ、今夜は図書館に行きます。 | — | acceptable | ええ、今夜は図書館に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0104 | pilot_dev | N5 | あの、今夜はカフェに行きます。 | — | acceptable | あの、今夜はカフェに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0105 | pilot_dev | N5 | その、今夜は病院に行きます。 | — | acceptable | その、今夜は病院に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0106 | pilot_dev | N4 | うーん、今夜は学校に行きます。 | — | acceptable | うーん、今夜は学校に行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0107 | pilot_dev | N5 | まあ、今夜はレストランに行きます。 | — | acceptable | まあ、今夜はレストランに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0108 | pilot_dev | N5 | えっと、今夜はコンビニに行きます。 | — | acceptable | えっと、今夜はコンビニに行きます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0109 | pilot_dev | N4 | まだ終えていません。 | 숙제를 끝냈는지 물었습니다. | acceptable | まだ終えていません。 | — | 문맥상 완결된 짧은 문장으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0110 | pilot_dev | N5 | 図書館です。 | 어디에서 공부하는지 물었습니다. | acceptable | 図書館です。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0111 | pilot_dev | N5 | 三時です。 | 몇 시에 만나는지 물었습니다. | acceptable | 三時です。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0112 | pilot_dev | N5 | 友達です。 | 함께 온 사람이 누구인지 물었습니다. | acceptable | 友達です。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0113 | pilot_dev | N4 | 明日です。 | 출발일이 언제인지 물었습니다. | acceptable | 明日です。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0114 | pilot_dev | N5 | はい、お願いします。 | 도움을 줄지 제안받았습니다. | acceptable | はい、お願いします。 | — | 문맥상 적절한 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0115 | pilot_dev | N5 | 二つです。 | 몇 개 필요한지 물었습니다. | acceptable | 二つです。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0116 | pilot_dev | N4 | 電車です。 | 무엇을 타고 왔는지 물었습니다. | acceptable | 電車です。 | — | 문맥상 완결된 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0117 | pilot_dev | N5 | 大丈夫です。 | 도움이 필요한지 물었습니다. | acceptable | 大丈夫です。 | — | 문맥상 적절한 짧은 대답으로 문법적 오류가 없습니다. | user_reviewed |
| JT-0118 | pilot_train | N5 | 先週は公園に行きました。それから写真を撮った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は公園に行きました。それから写真を撮った。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0119 | pilot_train | N4 | 先週は駅に行きました。それから切符を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は駅に行きました。それから切符を買った。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0120 | pilot_train | N5 | 先週はスーパーに行きました。それから野菜を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はスーパーに行きました。それから野菜を買った。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0121 | pilot_train | N5 | 先週は図書館に行きました。それから本を借りた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は図書館に行きました。それから本を借りた。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0122 | pilot_train | N5 | 先週はカフェに行きました。それからコーヒーを飲んだ。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はカフェに行きました。それからコーヒーを飲んだ。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0123 | pilot_train | N4 | 先週は病院に行きました。それから薬をもらった。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は病院に行きました。それから薬をもらった。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0124 | pilot_train | N5 | 先週は学校に行きました。それから授業を受けた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は学校に行きました。それから授業を受けた。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0125 | pilot_train | N5 | 先週はレストランに行きました。それから昼ご飯を食べた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はレストランに行きました。それから昼ご飯を食べた。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0126 | pilot_train | N4 | 先週はコンビニに行きました。それから新聞を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はコンビニに行きました。それから新聞を買った。 | — | 정중체와 보통체가 혼용되었으나, 주어진 문맥상 문법적 오류로 판단하지 않습니다. | user_reviewed |
| JT-0127 | pilot_train | N5 | この道なら、公園まで歩いて行けます。 | — | acceptable | この道なら、公園まで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0128 | pilot_train | N5 | この道なら、駅まで歩いて行けます。 | — | acceptable | この道なら、駅まで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0129 | pilot_train | N4 | この道なら、スーパーまで歩いて行けます。 | — | acceptable | この道なら、スーパーまで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0130 | pilot_train | N5 | この道なら、図書館まで歩いて行けます。 | — | acceptable | この道なら、図書館まで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0131 | pilot_train | N5 | この道なら、カフェまで歩いて行けます。 | — | acceptable | この道なら、カフェまで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0132 | pilot_train | N5 | この道なら、病院まで歩いて行けます。 | — | acceptable | この道なら、病院まで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0133 | pilot_train | N4 | この道なら、学校まで歩いて行けます。 | — | acceptable | この道なら、学校まで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0134 | pilot_train | N5 | この道なら、レストランまで歩いて行けます。 | — | acceptable | この道なら、レストランまで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0135 | pilot_train | N5 | この道なら、コンビニまで歩いて行けます。 | — | acceptable | この道なら、コンビニまで歩いて行けます。 | — | 문법적 오류가 없습니다. | user_reviewed |
| JT-0136 | pilot_dev | N4 | 明後日は公園を行きます。 | — | needs_correction | 明後日は公園に行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0137 | pilot_dev | N5 | 明後日は駅を行きます。 | — | needs_correction | 明後日は駅に行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0138 | pilot_dev | N5 | 明後日はスーパーを行きます。 | — | needs_correction | 明後日はスーパーに行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0139 | pilot_dev | N4 | 明後日は図書館を行きます。 | — | needs_correction | 明後日は図書館に行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0140 | pilot_dev | N5 | 明後日はカフェを行きます。 | — | needs_correction | 明後日はカフェに行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0141 | pilot_dev | N5 | 明後日は病院を行きます。 | — | needs_correction | 明後日は病院に行きます。 | particle_misuse | 목적지로의 이동을 나타내는 동사 '行く' 앞에는 조사 'に' 또는 'へ'가 적절합니다. | user_reviewed |
| JT-0142 | pilot_train | N5 | 昨日は学校を本を買いました。 | — | needs_correction | 昨日は学校で本を買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0143 | pilot_train | N4 | 昨日は売店を傘を買いました。 | — | needs_correction | 昨日は売店で傘を買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0144 | pilot_train | N5 | 昨日はコンビニを飲み物を買いました。 | — | needs_correction | 昨日はコンビニで飲み物を買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0145 | pilot_train | N5 | 昨日は書店を雑誌を買いました。 | — | needs_correction | 昨日は書店で雑誌を買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0146 | pilot_train | N4 | 昨日は神社をお守りを買いました。 | — | needs_correction | 昨日は神社でお守りを買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0147 | pilot_train | N5 | 昨日は駅前を弁当を買いました。 | — | needs_correction | 昨日は駅前で弁当を買いました。 | particle_misuse | 동작이 일어나는 장소를 나타낼 때는 조사 'で'를 사용해야 합니다. | user_reviewed |
| JT-0148 | pilot_train | N5 | 学校で図書室があります。 | — | needs_correction | 学校に図書室があります。 | particle_misuse | 사물의 존재 장소를 나타내는 동사 'ある' 앞에는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0149 | pilot_train | N4 | ホテルで荷物があります。 | — | needs_correction | ホテルに荷物があります。 | particle_misuse | 사물의 존재 장소를 나타내는 동사 'ある' 앞에는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0150 | pilot_train | N5 | 銀行でATMがあります。 | — | needs_correction | 銀行にATMがあります。 | particle_misuse | 사물의 존재 장소를 나타내는 동사 'ある' 앞에는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0151 | pilot_train | N5 | 会社で会議室があります。 | — | needs_correction | 会社に会議室があります。 | particle_misuse | 사물의 존재 장소를 나타내는 동사 'ある' 앞에는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0152 | pilot_train | N5 | 市役所で相談窓口があります。 | — | needs_correction | 市役所に相談窓口があります。 | particle_misuse | 사물의 존재 장소를 나타내는 동사 'ある' 앞에는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0153 | pilot_dev | N4 | 毎朝、手紙を書きくます。 | — | needs_correction | 毎朝、手紙を書きます。 | verb_conjugation | 5단 동사 '書く'의 ます형 접속은 어미를 い단으로 바꾼 '書きます'가 맞습니다. | user_reviewed |
| JT-0154 | pilot_dev | N5 | 週末に服を買うます。 | — | needs_correction | 週末に服を買います。 | verb_conjugation | 5단 동사 '買う'의 ます형 접속은 어미를 い단으로 바꾼 '買います'가 맞습니다. | user_reviewed |
| JT-0155 | pilot_dev | N5 | 駅で友達を待つます。 | — | needs_correction | 駅で友達を待ちます。 | verb_conjugation | 5단 동사 '待つ'의 ます형 접속은 어미를 い단으로 바꾼 '待ちます'가 맞습니다. | user_reviewed |
| JT-0156 | pilot_dev | N4 | 先生の話を聞くます。 | — | needs_correction | 先生の話を聞きます。 | verb_conjugation | 5단 동사 '聞く'의 ます형 접속은 어미를 い단으로 바꾼 '聞きます'가 맞습니다. | user_reviewed |
| JT-0157 | pilot_dev | N5 | 日本語で話すます。 | — | needs_correction | 日本語で話します。 | verb_conjugation | 5단 동사 '話す'의 ます형 접속은 어미를 い단으로 바꾼 '話します'가 맞습니다. | user_reviewed |
| JT-0158 | pilot_dev | N5 | 公園で遊ぶます。 | — | needs_correction | 公園で遊びます。 | verb_conjugation | 5단 동사 '遊ぶ'의 ます형 접속은 어미를 い단으로 바꾼 '遊びます'가 맞습니다. | user_reviewed |
| JT-0159 | pilot_train | N4 | 昨日、手紙を書きくました。 | — | needs_correction | 昨日、手紙を書きました。 | verb_conjugation | 5단 동사 '書く'의 과거 정중형은 '書きました'가 맞습니다. | user_reviewed |
| JT-0160 | pilot_train | N5 | 先週、服を買うました。 | — | needs_correction | 先週、服を買いました。 | verb_conjugation | 5단 동사 '買う'의 과거 정중형은 '買いました'가 맞습니다. | user_reviewed |
| JT-0161 | pilot_train | N5 | 駅で友達を待つました。 | — | needs_correction | 駅で友達を待ちました。 | verb_conjugation | 5단 동사 '待つ'의 과거 정중형은 '待ちました'가 맞습니다. | user_reviewed |
| JT-0162 | pilot_train | N5 | 先生の話を聞くました。 | — | needs_correction | 先生の話を聞きました。 | verb_conjugation | 5단 동사 '聞く'의 과거 정중형은 '聞きました'가 맞습니다. | user_reviewed |
| JT-0163 | pilot_train | N4 | 日本語で話すました。 | — | needs_correction | 日本語で話しました。 | verb_conjugation | 5단 동사 '話す'의 과거 정중형은 '話しました'가 맞습니다. | user_reviewed |
| JT-0164 | pilot_train | N5 | 公園で遊ぶました。 | — | needs_correction | 公園で遊びました。 | verb_conjugation | 5단 동사 '遊ぶ'의 과거 정중형은 '遊びました'가 맞습니다. | user_reviewed |
| JT-0165 | pilot_train | N5 | この用紙に住所を書きてください。 | — | needs_correction | この用紙に住所を書いてください。 | verb_conjugation | 5단 동사 '書く'의 て형은 '書いて'로 활용됩니다. | user_reviewed |
| JT-0166 | pilot_train | N4 | 少し待ちてください。 | — | needs_correction | 少し待ってください。 | verb_conjugation | 5단 동사 '待つ'의 て형은 '待って'로 활용됩니다 (촉음편). | user_reviewed |
| JT-0167 | pilot_train | N5 | この本を読みてください。 | — | needs_correction | この本を読んでください。 | verb_conjugation | 5단 동사 '読む'の て형은 '読んで'로 활용됩니다 (발음편). | user_reviewed |
| JT-0168 | pilot_train | N5 | もう一度話すてください。 | — | needs_correction | もう一度話してください。 | verb_conjugation | 5단 동사 '話す'의 て형은 '話して'로 활용됩니다. | user_reviewed |
| JT-0169 | pilot_train | N4 | 駅まで歩くてください。 | — | needs_correction | 駅まで歩いてください。 | verb_conjugation | 5단 동사 '歩く'의 て형은 '歩いて'로 활용됩니다 (이음편). | user_reviewed |
| JT-0170 | pilot_dev | N5 | 昨日は寒いかったです。 | — | needs_correction | 昨日は寒かったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0171 | pilot_dev | N5 | 料理は美味しいかったです。 | — | needs_correction | 料理は美味しかったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0172 | pilot_dev | N5 | 鞄は重いかったです。 | — | needs_correction | 鞄は重かったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0173 | pilot_dev | N4 | 試験は難しいかったです。 | — | needs_correction | 試験は難しかったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0174 | pilot_dev | N5 | 旅行は楽しいかったです。 | — | needs_correction | 旅行は楽しかったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0175 | pilot_dev | N5 | 部屋は暑いかったです。 | — | needs_correction | 部屋は暑かったです。 | adjective_conjugation | 이형용사의 과거형은 어미 'い'를 떼고 '〜かった'를 붙입니다. | user_reviewed |
| JT-0176 | pilot_train | N4 | この時計は高いくないです。 | — | needs_correction | この時計は高くないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0177 | pilot_train | N5 | 道は長いくないです。 | — | needs_correction | 道は長くないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0178 | pilot_train | N5 | 今日は忙しいくないです。 | — | needs_correction | 今日は忙しくないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0179 | pilot_train | N4 | この服は安いくないです。 | — | needs_correction | この服は安くないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0180 | pilot_train | N5 | 荷物は大きいくないです。 | — | needs_correction | 荷物は大きくないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0181 | pilot_train | N5 | 駅は遠いくないです。 | — | needs_correction | 駅は遠くないです。 | adjective_conjugation | 이형용사의 부정형은 어미 'い'를 떼고 '〜くない'를 붙입니다. | user_reviewed |
| JT-0182 | pilot_train | N5 | この店は安いて便利です。 | — | needs_correction | この店は安くて便利です。 | adjective_conjugation | 이형용사의 연결형(て형)은 어미 'い'를 '〜くて'로 바꿉니다. | user_reviewed |
| JT-0183 | pilot_train | N4 | 今日は寒いて大変です。 | — | needs_correction | 今日は寒くて大変です。 | adjective_conjugation | 이형용사의 연결형(て형)은 어미 'い'를 '〜くて'로 바꿉니다. | user_reviewed |
| JT-0184 | pilot_train | N5 | 道は長いて暗いです。 | — | needs_correction | 道は長くて暗いです。 | adjective_conjugation | 이형용사의 연결형(て형)은 어미 'い'를 '〜くて'로 바꿉니다. | user_reviewed |
| JT-0185 | pilot_train | N5 | 鞄は軽いて便利です。 | — | needs_correction | 鞄は軽くて便利です。 | adjective_conjugation | 이형용사의 연결형(て형)은 어미 'い'를 '〜くて'로 바꿉니다. | user_reviewed |
| JT-0186 | pilot_train | N4 | 料理は辛いて美味しいです。 | — | needs_correction | 料理は辛くて美味しいです。 | adjective_conjugation | 이형용사의 연결형(て형)은 어미 'い'를 '〜くて'로 바꿉니다. | user_reviewed |
| JT-0187 | pilot_dev | N5 | 今朝は寒いだです。 | — | needs_correction | 今朝は寒いです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0188 | pilot_dev | N5 | この鞄は大きいだです。 | — | needs_correction | この鞄は大きいです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0189 | pilot_dev | N4 | 料理は美味しいだです。 | — | needs_correction | 料理は美味しいです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0190 | pilot_dev | N5 | 駅は遠いだです。 | — | needs_correction | 駅は遠いです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0191 | pilot_dev | N5 | この服は安いだです。 | — | needs_correction | この服は安いです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0192 | pilot_dev | N5 | 道は長いだです。 | — | needs_correction | 道は長いです。 | copula_conjugation | 이형용사를 정중하게 종결할 때는 'だ' 없이 'です'만 붙입니다. | user_reviewed |
| JT-0193 | pilot_train | N4 | この町は静かなです。 | — | needs_correction | この町は静かです。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0194 | pilot_train | N5 | 先生は元気なです。 | — | needs_correction | 先生は元気です。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0195 | pilot_train | N5 | 問題は簡単なです。 | — | needs_correction | 問題は簡単です。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0196 | pilot_train | N4 | この店は有名なです。 | — | needs_correction | この店は有名です。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0197 | pilot_train | N5 | 説明は自然なです。 | — | needs_correction | 説明は自然です。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0198 | pilot_train | N5 | 今日は特別なです。 | — | needs_correction | 今日は特別です。 | copula_conjugation | 나형용사를 정중하게 종결할 때는 'な'가 아니라 'です'가 결합합니다. | user_reviewed |
| JT-0199 | pilot_train | N4 | 私は旅行が好きだです。 | — | needs_correction | 私は旅行が好きです。 | copula_conjugation | 나형용사의 정중형 종결은 'だ' 없이 'です'가 직접 붙습니다. | user_reviewed |
| JT-0200 | pilot_train | N5 | 妹は音楽が好きだです。 | — | needs_correction | 妹は音楽が好きです。 | copula_conjugation | 나형용사의 정중형 종결은 'だ' 없이 'です'가 직접 붙습니다. | user_reviewed |
| JT-0201 | pilot_train | N5 | 友達は映画が好きだです。 | — | needs_correction | 友達は映画が好きです。 | copula_conjugation | 나형용사의 정중형 종결은 'だ' 없이 'です'가 직접 붙습니다. | user_reviewed |
| JT-0202 | pilot_train | N5 | 父は料理が好きだです。 | — | needs_correction | 父は料理が好きです。 | copula_conjugation | 나형용사의 정중형 종결은 'だ' 없이 'です'가 직접 붙습니다. | user_reviewed |
| JT-0203 | pilot_train | N4 | 先生は読書が好きだです。 | — | needs_correction | 先生は読書が好きです。 | copula_conjugation | 나형용사의 정중형 종결은 'だ' 없이 'です'가 직접 붙습니다. | user_reviewed |
| JT-0204 | pilot_train | N5 | 静か町に住んでいます。 | — | needs_correction | 静かな町に住んでいます。 | modifier_connection | 나형용사가 명사를 수식할 때는 어미가 '〜な' 형태가 되어야 합니다. | user_reviewed |
| JT-0205 | pilot_train | N5 | 有名店で食べました。 | — | acceptable | 有名店で食べました。 | — | '有名店'은 하나의 합성 명사로 쓰이므로 문법적 오류가 없습니다. | user_reviewed |
| JT-0206 | pilot_train | N4 | 元気子どもが遊んでいます。 | — | needs_correction | 元気な子どもが遊んでいます。 | modifier_connection | 나형용사가 명사를 수식할 때는 어미가 '〜な' 형태가 되어야 합니다. | user_reviewed |
| JT-0207 | pilot_train | N5 | 簡単問題を解きました。 | — | needs_correction | 簡単な問題を解きました。 | modifier_connection | 나형용사가 명사를 수식할 때는 어미가 '〜な' 형태가 되어야 합니다. | user_reviewed |
| JT-0208 | pilot_train | N5 | 特別日になりました。 | — | needs_correction | 特別な日になりました。 | modifier_connection | 나형용사가 명사를 수식할 때는 어미가 '〜な' 형태가 되어야 합니다. | user_reviewed |
| JT-0209 | pilot_train | N4 | 自然日本語を話します。 | — | needs_correction | 自然な日本語を話します。 | modifier_connection | 나형용사가 명사를 수식할 때는 어미가 '〜な' 형태가 되어야 합니다. | user_reviewed |
| JT-0210 | pilot_train | N5 | 新しい安いな時計を買いました。 | — | needs_correction | 新しい安い時計を買いました。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않습니다. 두 이형용사를 연결할 땐 '〜くて'가 자연스럽습니다. | user_reviewed |
| JT-0211 | pilot_train | N5 | 大きいな鞄を持っています。 | — | needs_correction | 大きい鞄を持っています。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않으며, 연체사 '大きな'를 쓰는 것도 가능합니다. | user_reviewed |
| JT-0212 | pilot_train | N5 | 美味しいな料理を食べました。 | — | needs_correction | 美味しい料理を食べました。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않고 원형 그대로 수식합니다. | user_reviewed |
| JT-0213 | pilot_train | N4 | 長いな道を歩きました。 | — | needs_correction | 長い道を歩きました。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않고 원형 그대로 수식합니다. | user_reviewed |
| JT-0214 | pilot_train | N5 | 寒いな朝でした。 | — | needs_correction | 寒い朝でした。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않고 원형 그대로 수식합니다. | user_reviewed |
| JT-0215 | pilot_train | N5 | 楽しいな旅行でした。 | — | needs_correction | 楽しい旅行でした。 | modifier_connection | 이형용사가 명사를 수식할 때는 'な'가 붙지 않고 원형 그대로 수식합니다. | user_reviewed |
| JT-0216 | pilot_train | N4 | これは先生を本です。 | — | needs_correction | これは先生の本です。 | modifier_connection | 명사와 명사를 연결하여 소속이나 소유를 나타낼 때는 조사 'の'를 사용합니다. | user_reviewed |
| JT-0217 | pilot_train | N5 | あれは友達を傘です。 | — | needs_correction | あれは友達の傘です。 | modifier_connection | 명사와 명사를 연결하여 소유를 나타낼 때는 조사 'の'를 사용합니다. | user_reviewed |
| JT-0218 | pilot_train | N5 | これは父を時計です。 | — | needs_correction | これは父の時計です。 | modifier_connection | 명사와 명사를 연결하여 소유를 나타낼 때는 조사 'の'를 사용합니다. | user_reviewed |
| JT-0219 | pilot_train | N4 | それは妹を鞄です。 | — | needs_correction | それは妹の鞄です。 | modifier_connection | 명사와 명사를 연결하여 소유를 나타낼 때는 조사 'の'를 사용합니다. | user_reviewed |
| JT-0220 | pilot_train | N5 | これは店をカードです。 | — | needs_correction | これは店のカードです。 | modifier_connection | 명사와 명사를 연결하여 소속을 나타낼 때는 조사 'の'를 사용합니다. | user_reviewed |
| JT-0221 | pilot_train | N5 | 昨日は図書館で勉強します。 | — | needs_correction | 昨日は図書館で勉強しました。 | tense_mismatch | '昨日'라는 과거 시점을 나타내는 부사에 맞게 서술어도 과거형 'しました'가 되어야 합니다. | user_reviewed |
| JT-0222 | pilot_train | N5 | 先週は東京へ行きます。 | — | needs_correction | 先週は東京へ行きました。 | tense_mismatch | '先週'라는 과거 시점을 나타내는 부사에 맞게 서술어도 과거형 '行きました'가 되어야 합니다. | user_reviewed |
| JT-0223 | pilot_train | N4 | 去年は日本語を習います。 | — | needs_correction | 去年は日本語を習いました。 | tense_mismatch | '去年'이라는 과거 시점을 나타내는 부사에 맞게 서술어도 과거형 '習いました'가 되어야 합니다. | user_reviewed |
| JT-0224 | pilot_train | N5 | 一時間前に昼ご飯を食べます。 | — | needs_correction | 一時間前に昼ご飯を食べました。 | tense_mismatch | '一時間前'이라는 과거 시점에 맞게 서술어도 과거형 '食べました'가 되어야 합니다. | user_reviewed |
| JT-0225 | pilot_train | N5 | 昨夜は映画を見ます。 | — | needs_correction | 昨夜は映画を見ました。 | tense_mismatch | '昨夜'라는 과거 시점을 나타내는 부사에 맞게 서술어도 과거형 '見ました'가 되어야 합니다. | user_reviewed |
| JT-0226 | pilot_train | N4 | 二日前はホテルに泊まります。 | — | needs_correction | 二日前はホテルに泊まりました。 | tense_mismatch | '二日前'이라는 과거 시점에 맞게 서술어도 과거형 '泊まりました'가 되어야 합니다. | user_reviewed |
| JT-0227 | pilot_train | N5 | 明日は病院へ行きました。 | — | needs_correction | 明日は病院へ行きます。 | tense_mismatch | '明日'라는 미래 시점과 과거형 서술어 '行きました'가 문법적으로 모순됩니다. 미래형(비과거형)을 써야 합니다. | user_reviewed |
| JT-0228 | pilot_train | N5 | 来週は試験を受けました。 | — | needs_correction | 来週は試験を受けます。 | tense_mismatch | '来週'라는 미래 시점과 과거형 서술어 '受けました'가 모순되므로 '受けます'로 수정해야 합니다. | user_reviewed |
| JT-0229 | pilot_train | N4 | 来年は京都に住みました。 | — | needs_correction | 来年は京都に住みます。 | tense_mismatch | '来年'이라는 미래 시점과 과거형 서술어가 모순되므로 비과거형 '住みます'로 수정해야 합니다. | user_reviewed |
| JT-0230 | pilot_train | N5 | 一時間後に出発しました。 | — | needs_correction | 一時間後に出発します。 | tense_mismatch | '一時間後'라는 미래 시점과 과거형 서술어가 모순되므로 비과거형 '出発します'로 수정해야 합니다. | user_reviewed |
| JT-0231 | pilot_train | N5 | 明日の夜は友達に会いました。 | — | needs_correction | 明日の夜は友達に会います。 | tense_mismatch | '明日の夜'라는 미래 시점과 과거형 서술어가 모순되므로 비과거형 '会います'로 수정해야 합니다. | user_reviewed |
| JT-0232 | pilot_train | N5 | 来月は新しい仕事を始めました。 | — | needs_correction | 来月は新しい仕事を始めます。 | tense_mismatch | '来月'이라는 미래 시점과 과거형 서술어가 모순되므로 비과거형 '始めます'로 수정해야 합니다. | user_reviewed |
| JT-0233 | pilot_train | N4 | 旅行は明日始まりました。 | — | needs_correction | 旅行は明日始まります。 | tense_mismatch | '明日'라는 미래 시점과 과거형 서술어 '始まりました'가 모순되므로 비과거형을 써야 합니다. | user_reviewed |
| JT-0234 | pilot_train | N5 | 会議は来週終わりました。 | — | needs_correction | 会議は来週終わります。 | tense_mismatch | '来週'라는 미래 시점과 과거형 서술어 '終わりました'가 모순되므로 비과거형을 써야 합니다. | user_reviewed |
| JT-0235 | pilot_train | N5 | 工事は来年始まりました。 | — | needs_correction | 工事は来年始まります。 | tense_mismatch | '来年'이라는 미래 시점과 과거형 서술어 '始まりました'가 모순되므로 비과거형을 써야 합니다. | user_reviewed |
| JT-0236 | pilot_train | N4 | 説明会は一時間後に始まりました。 | — | needs_correction | 説明会は一時間後に始まります。 | tense_mismatch | '一時間後'라는 미래 시점과 과거형 서술어 '始まりました'가 모순되므로 비과거형을 써야 합니다. | user_reviewed |
| JT-0237 | pilot_train | N5 | イベントは今夜始まりました。 | — | needs_correction | イベントは今夜始まります。 | tense_mismatch | 다가올 '今夜'라는 시점과 과거형 서술어 '始まりました'가 모순되므로 비과거형을 써야 합니다. | user_reviewed |
| JT-0238 | pilot_train | N5 | 昨日は学校を本を読むました。 | — | needs_correction | 昨日は学校で本を読みました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '読む'의 과거 정중형은 '読みました'입니다. | user_reviewed |
| JT-0239 | pilot_train | N4 | 先週は図書館を新聞を読むました。 | — | needs_correction | 先週は図書館で新聞を読みました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '読む'의 과거 정중형은 '読みました'입니다. | user_reviewed |
| JT-0240 | pilot_train | N5 | 昨日は店を服を買うました。 | — | needs_correction | 昨日は店で服を買いました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '買う'의 과거 정중형은 '買いました'입니다. | user_reviewed |
| JT-0241 | pilot_train | N5 | 先週は公園を友達と話すました。 | — | needs_correction | 先週は公園で友達と話しました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '話す'의 과거 정중형은 '話しました'입니다. | user_reviewed |
| JT-0242 | pilot_train | N5 | 昨日は駅を先生を待つました。 | — | needs_correction | 昨日は駅で先生を待ちました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '待つ'의 과거 정중형은 '待ちました'입니다. | user_reviewed |
| JT-0243 | pilot_train | N4 | 先週はカフェを手紙を書くました。 | — | needs_correction | 先週はカフェで手紙を書きました。 | particle_misuse, verb_conjugation | 장소 조사는 'で'가 맞으며, '書く'의 과거 정중형은 '書きました'입니다. | user_reviewed |
| JT-0244 | pilot_train | N5 | 白い小さいな犬が庭でいます。 | — | needs_correction | 白い小さい犬が庭にいます。 | modifier_connection, particle_misuse | 이형용사는 명사 수식 시 'な'가 붙지 않으며, 'いる' 앞의 존재 장소는 조사 'に'를 사용합니다. | user_reviewed |
| JT-0245 | pilot_train | N5 | 大きいな鞄が部屋であります。 | — | needs_correction | 大きい鞄が部屋にあります。 | modifier_connection, particle_misuse | 이형용사 뒤에 'な'를 붙일 수 없으며, 존재 동사 'ある' 앞의 장소는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0246 | pilot_train | N4 | 静か町で公園があります。 | — | needs_correction | 静かな町に公園があります。 | modifier_connection, particle_misuse | 나형용사 수식형 '静かな'가 맞으며, 존재 동사 'ある' 앞의 장소는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0247 | pilot_train | N5 | 有名店で時計があります。 | — | needs_correction | 有名店に時計があります。 | particle_misuse | 사물의 존재를 나타내는 동사 あります(ある)와 함께 쓰일 때, 장소 조사는 동작 장소의 で가 아니라 존재 장소의 に를 사용합니다. (평가 기준 1: 조사 오류) | user_reviewed |
| JT-0248 | pilot_train | N5 | 安いなホテルでカフェがあります。 | — | needs_correction | 安いホテルにカフェがあります。 | modifier_connection, particle_misuse | 이형용사에는 'な'가 붙지 않으며, 존재 동사 'ある' 앞의 장소는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0249 | pilot_train | N4 | 自然日本語の本が机であります。 | — | needs_correction | 自然な日本語の本が机にあります。 | modifier_connection, particle_misuse | 나형용사의 수식형인 '自然な'가 맞으며, 존재 동사 'ある' 앞의 장소는 조사 'に'를 사용해야 합니다. | user_reviewed |
| JT-0250 | pilot_train | N5 | 昨日の料理は美味しいかったので、明日も食べました。 | — | needs_correction | 昨日の料理は美味しかったので、明日も食べます。 | adjective_conjugation, tense_mismatch | 이형용사의 과거형은 '美味しかった'이며, 미래 시점인 '明日'와 맞물리도록 서술어는 '食べます'가 되어야 합니다. | user_reviewed |
| JT-0251 | pilot_train | N5 | 昨日は寒いかったので、明日は家にいました。 | — | needs_correction | 昨日は寒かったので、明日は家にいます。 | adjective_conjugation, tense_mismatch | 이형용사 과거형은 '寒かった'이며, '明日'에 호응하는 서술어는 'います'가 되어야 문법적 모순이 없습니다. | user_reviewed |
| JT-0252 | pilot_train | N5 | 先週は忙しいかったですが、来週は休みました。 | — | needs_correction | 先週は忙しかったですが、来週は休みます。 | adjective_conjugation, tense_mismatch | 이형용사 과거형은 '忙しかった'이며, 미래 시점 '来週'와 호응하는 서술어는 '休みます'입니다. | user_reviewed |
| JT-0253 | pilot_train | N4 | 昨日の鞄は重いかったので、明日は使いませんでした。 | — | needs_correction | 昨日の鞄は重かったので、明日は使いません。 | adjective_conjugation, tense_mismatch | 이형용사 과거형은 '重かった'이며, '明日'와 호응하는 부정 서술어는 '使いません'입니다. | user_reviewed |
| JT-0254 | pilot_train | N5 | 去年の旅行は楽しいかったので、来年も行きました。 | — | needs_correction | 去年の旅行は楽しかったので、来年も行きます。 | adjective_conjugation, tense_mismatch | 이형용사 과거형은 '楽しかった'이며, 미래인 '来年'에 호응하는 서술어는 '行きます'입니다. | user_reviewed |
| JT-0255 | pilot_train | N5 | 昨夜は暑いかったですが、明日は涼しかったです。 | — | needs_correction | 昨夜は暑かったですが、明日は涼しいです。 | adjective_conjugation, tense_mismatch | 이형용사 과거형은 '暑かった'이며, 미래인 '明日'의 상태를 나타낼 때는 '涼しいです'(비과거형)를 씁니다. | user_reviewed |
| JT-0256 | pilot_train | N4 | （無言） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （無言） | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0257 | pilot_train | N5 | ［無音］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［無音］ | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0258 | pilot_train | N5 | ……（沈黙） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ……（沈黙） | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0259 | pilot_train | N4 | （返答なし） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （返答なし） | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0260 | pilot_train | N5 | ［発話なし］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［発話なし］ | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0261 | pilot_train | N5 | ……？ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ……？ | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0262 | pilot_train | N5 | （考え中） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （考え中） | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0263 | pilot_train | N4 | ［沈黙が続く］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［沈黙が続く］ | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0264 | pilot_train | N5 | （声なし） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （声なし） | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0265 | pilot_train | N5 | えっと…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | えっと…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0266 | pilot_train | N4 | あのですね…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | あのですね…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0267 | pilot_train | N5 | うーん…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | うーん…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0268 | pilot_train | N5 | その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | その…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0269 | pilot_train | N4 | まあ…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | まあ…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0270 | pilot_train | N5 | ええと、その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | ええと、その…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0271 | pilot_train | N5 | あのう…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | あのう…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0272 | pilot_train | N5 | そうですね…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | そうですね…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0273 | pilot_train | N4 | ちょっと、その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | ちょっと、その…… | — | 의미를 이루는 문장이 없어 교정 대상이 아니며, 필러 자체는 오류가 아닙니다. | user_reviewed |
| JT-0274 | pilot_dev | N5 | 今朝、駅で先生に | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 今朝、駅で先生に | — | 문장이 미완성 상태이므로 의도한 동사를 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0275 | pilot_dev | N5 | 来週、友達と映画を | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 来週、友達と映画を | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0276 | pilot_dev | N4 | この料理を作ったのは | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | この料理を作ったのは | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0277 | pilot_dev | N5 | もし時間があったら | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | もし時間があったら | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0278 | pilot_dev | N5 | 昨日、病院から | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 昨日、病院から | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0279 | pilot_dev | N4 | 日本に来てからずっと | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 日本に来てからずっと | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0280 | pilot_dev | N5 | 私が一番好きなのは | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 私が一番好きなのは | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0281 | pilot_dev | N5 | 雨が降らなければ | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 雨が降らなければ | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0282 | pilot_dev | N5 | その本を読んだあとで | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | その本を読んだあとで | — | 문장이 미완성 상태이므로 후속 내용을 임의로 추측하여 교정하지 않습니다. | user_reviewed |
| JT-0283 | pilot_train | N4 | 今日は［音声欠落］です。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 今日は［音声欠落］です。 | — | 음성 결락으로 인해 정확한 문장 구조를 알 수 없어 임의로 교정하지 않습니다. | user_reviewed |
| JT-0284 | pilot_train | N5 | 明日は［判別不能］へ行きます。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 明日は［判別不能］へ行きます。 | — | 결락된 부분이 있어 임의로 내용을 채워 넣어 교정하지 않습니다. | user_reviewed |
| JT-0285 | pilot_train | N5 | ［環境音のみ］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［環境音のみ］ | — | 실제 발화 내용이 없어 교정 대상이 아닙니다. | user_reviewed |
| JT-0286 | pilot_train | N4 | 駅で［一部欠落］を買いました。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 駅で［一部欠落］を買いました。 | — | 결락된 부분이 있어 임의로 내용을 채워 넣어 교정하지 않습니다. | user_reviewed |
| JT-0287 | pilot_train | N5 | 昨日は［音声なし］。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 昨日は［音声なし］。 | — | 음성 결락으로 인해 서술어를 알 수 없어 추측 교정하지 않습니다. | user_reviewed |
| JT-0288 | pilot_train | N5 | ［録音失敗］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［録音失敗］ | — | 녹음이 없어 교정 대상 문장이 존재하지 않습니다. | user_reviewed |
| JT-0289 | pilot_train | N4 | 先生が［聞き取り不能］と言いました。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 先生が［聞き取り不能］と言いました。 | — | 결락된 부분의 내용을 알 수 없어 추측 교정하지 않습니다. | user_reviewed |
| JT-0290 | pilot_train | N5 | この本は［雑音区間］です。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | この本は［雑音区間］です。 | — | 결락된 부분의 내용을 알 수 없어 추측 교정하지 않습니다. | user_reviewed |
| JT-0291 | pilot_train | N5 | ［発話区間なし］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［発話区間なし］ | — | 실제 발화가 없으므로 문법 교정 대상이 아닙니다. | user_reviewed |
| JT-0292 | pilot_train | N5 | I will visit the library tomorrow. | — | insufficient_evidence | I will visit the library tomorrow. | — | 타 언어(영어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0293 | pilot_train | N4 | Please wait here for a moment. | — | insufficient_evidence | Please wait here for a moment. | — | 타 언어(영어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0294 | pilot_train | N5 | My friend bought a new camera. | — | insufficient_evidence | My friend bought a new camera. | — | 타 언어(영어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0295 | pilot_train | N5 | We studied Japanese last night. | — | insufficient_evidence | We studied Japanese last night. | — | 타 언어(영어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0296 | pilot_train | N4 | 내일은 병원에 갈 예정입니다. | — | insufficient_evidence | 내일은 병원에 갈 예정입니다. | — | 타 언어(한국어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0297 | pilot_train | N5 | 친구와 도서관에서 공부했습니다. | — | insufficient_evidence | 친구와 도서관에서 공부했습니다. | — | 타 언어(한국어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0298 | pilot_train | N5 | 이 가방은 생각보다 무겁습니다. | — | insufficient_evidence | 이 가방은 생각보다 무겁습니다. | — | 타 언어(한국어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0299 | pilot_train | N4 | 다시 한번 천천히 말해주세요. | — | insufficient_evidence | 다시 한번 천천히 말해주세요. | — | 타 언어(한국어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
| JT-0300 | pilot_train | N5 | 오늘 저녁에는 집에서 쉽니다. | — | insufficient_evidence | 오늘 저녁에는 집에서 쉽니다. | — | 타 언어(한국어)는 문법 교정 대상이 아니며 번역 대상으로 분류합니다. | user_reviewed |
