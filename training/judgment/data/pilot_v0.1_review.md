# 일본어 판단 LoRA 파일럿 v0.1 — 검수용 보기

상태: 300문항 모두 `provisional`. 이 문서는 검수 보기이며 JSONL이 정답 원본입니다.
Qwen3-14B는 어휘·상황 후보만 제공했고 판단·교정·edit는 결정론적 템플릿으로 만들었습니다.
승인 전 학습에는 사용하지 않습니다. 개인 검수자 식별자는 기록하지 않습니다.

| ID | split | 수준 | 입력 | 문맥 | 판단안 | 교정안 | 오류 유형 | 근거 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JT-0001 | pilot_train | N5 | 来月は公園に行きます。 | — | acceptable | 来月は公園に行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0002 | pilot_train | N5 | 来月は駅に行きます。 | — | acceptable | 来月は駅に行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0003 | pilot_train | N4 | 来月はスーパーに行きます。 | — | acceptable | 来月はスーパーに行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0004 | pilot_train | N5 | 来月は図書館に行きます。 | — | acceptable | 来月は図書館に行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0005 | pilot_train | N5 | 来月はカフェに行きます。 | — | acceptable | 来月はカフェに行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0006 | pilot_train | N4 | 来月は病院に行きます。 | — | acceptable | 来月は病院に行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0007 | pilot_train | N5 | 来月は学校に行きます。 | — | acceptable | 来月は学校に行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0008 | pilot_train | N5 | 来月はレストランに行きます。 | — | acceptable | 来月はレストランに行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0009 | pilot_train | N4 | 来月はコンビニに行きます。 | — | acceptable | 来月はコンビニに行きます。 | — | 목적지에는 に를 사용할 수 있습니다. | provisional |
| JT-0010 | pilot_train | N5 | 駅で切符を買いました。 | — | acceptable | 駅で切符を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0011 | pilot_train | N5 | スーパーで傘を買いました。 | — | acceptable | スーパーで傘を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0012 | pilot_train | N5 | 図書館で本を買いました。 | — | acceptable | 図書館で本を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0013 | pilot_train | N4 | カフェでコーヒーを買いました。 | — | acceptable | カフェでコーヒーを買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0014 | pilot_train | N5 | 病院で薬を買いました。 | — | acceptable | 病院で薬を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0015 | pilot_train | N5 | 学校でノートを買いました。 | — | acceptable | 学校でノートを買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0016 | pilot_train | N4 | レストランで昼ご飯を買いました。 | — | acceptable | レストランで昼ご飯を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0017 | pilot_train | N5 | コンビニで新聞を買いました。 | — | acceptable | コンビニで新聞を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0018 | pilot_train | N5 | ホテルで水を買いました。 | — | acceptable | ホテルで水を買いました。 | — | 동작이 일어난 장소에는 で가 적절합니다. | provisional |
| JT-0019 | pilot_dev | N4 | 朝、公園をゆっくり歩きました。 | — | acceptable | 朝、公園をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0020 | pilot_dev | N5 | 朝、商店街をゆっくり歩きました。 | — | acceptable | 朝、商店街をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0021 | pilot_dev | N5 | 朝、橋をゆっくり歩きました。 | — | acceptable | 朝、橋をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0022 | pilot_dev | N5 | 朝、道をゆっくり歩きました。 | — | acceptable | 朝、道をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0023 | pilot_dev | N4 | 朝、駅前をゆっくり歩きました。 | — | acceptable | 朝、駅前をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0024 | pilot_dev | N5 | 朝、海岸をゆっくり歩きました。 | — | acceptable | 朝、海岸をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0025 | pilot_dev | N5 | 朝、森をゆっくり歩きました。 | — | acceptable | 朝、森をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0026 | pilot_dev | N4 | 朝、町をゆっくり歩きました。 | — | acceptable | 朝、町をゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0027 | pilot_dev | N5 | 朝、川沿いをゆっくり歩きました。 | — | acceptable | 朝、川沿いをゆっくり歩きました。 | — | 이동한 경로를 나타내는 を가 적절합니다. | provisional |
| JT-0028 | pilot_train | N5 | これは友達の本です。 | — | acceptable | これは友達の本です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0029 | pilot_train | N4 | これは先生の傘です。 | — | acceptable | これは先生の傘です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0030 | pilot_train | N5 | これは家族の鞄です。 | — | acceptable | これは家族の鞄です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0031 | pilot_train | N5 | これは隣人のスマホです。 | — | acceptable | これは隣人のスマホです。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0032 | pilot_train | N5 | これは店員の名札です。 | — | acceptable | これは店員の名札です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0033 | pilot_train | N4 | これは医者の筆記用具です。 | — | acceptable | これは医者の筆記用具です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0034 | pilot_train | N5 | これは学生のノートです。 | — | acceptable | これは学生のノートです。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0035 | pilot_train | N5 | これは観光客のカメラです。 | — | acceptable | これは観光客のカメラです。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0036 | pilot_train | N4 | これは職人の時計です。 | — | acceptable | これは職人の時計です。 | — | 명사 사이의 소유·관계에는 の가 적절합니다. | provisional |
| JT-0037 | pilot_train | N5 | こちらの用紙に名前を書いてください。 | — | acceptable | こちらの用紙に名前を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0038 | pilot_train | N5 | こちらの用紙に住所を書いてください。 | — | acceptable | こちらの用紙に住所を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0039 | pilot_train | N4 | こちらの用紙に電話番号を書いてください。 | — | acceptable | こちらの用紙に電話番号を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0040 | pilot_train | N5 | こちらの用紙に予定を書いてください。 | — | acceptable | こちらの用紙に予定を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0041 | pilot_train | N5 | こちらの用紙に答えを書いてください。 | — | acceptable | こちらの用紙に答えを書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0042 | pilot_train | N5 | こちらの用紙に感想を書いてください。 | — | acceptable | こちらの用紙に感想を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0043 | pilot_train | N4 | こちらの用紙に理由を書いてください。 | — | acceptable | こちらの用紙に理由を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0044 | pilot_train | N5 | こちらの用紙に日付を書いてください。 | — | acceptable | こちらの用紙に日付を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0045 | pilot_train | N5 | こちらの用紙に番号を書いてください。 | — | acceptable | こちらの用紙に番号を書いてください。 | — | 書く의 て형과 요청 표현이 올바르게 연결됩니다. | provisional |
| JT-0046 | pilot_train | N4 | その本は厚くなかったです。 | — | acceptable | その本は厚くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0047 | pilot_train | N5 | その傘は高くなかったです。 | — | acceptable | その傘は高くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0048 | pilot_train | N5 | その鞄は重くなかったです。 | — | acceptable | その鞄は重くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0049 | pilot_train | N4 | そのスマホは安くなかったです。 | — | acceptable | そのスマホは安くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0050 | pilot_train | N5 | そのコーヒーは熱くなかったです。 | — | acceptable | そのコーヒーは熱くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0051 | pilot_train | N5 | その店の筆記用具は多くなかったです。 | — | acceptable | その店の筆記用具は多くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0052 | pilot_train | N5 | そのノートは大きくなかったです。 | — | acceptable | そのノートは大きくなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0053 | pilot_train | N4 | その服は新しくなかったです。 | — | acceptable | その服は新しくなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0054 | pilot_train | N5 | その時計は古くなかったです。 | — | acceptable | その時計は古くなかったです。 | — | 형용사의 과거 부정형이 적절합니다. | provisional |
| JT-0055 | pilot_train | N5 | 静かな町ですね。 | — | acceptable | 静かな町ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0056 | pilot_train | N4 | きれいな部屋ですね。 | — | acceptable | きれいな部屋ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0057 | pilot_train | N5 | 有名な店ですね。 | — | acceptable | 有名な店ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0058 | pilot_train | N5 | 広大な公園ですね。 | — | acceptable | 広大な公園ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0059 | pilot_train | N4 | 安全な道ですね。 | — | acceptable | 安全な道ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0060 | pilot_train | N5 | 便利なホテルですね。 | — | acceptable | 便利なホテルですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0061 | pilot_train | N5 | 立派な学校ですね。 | — | acceptable | 立派な学校ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0062 | pilot_train | N5 | 特別な場所ですね。 | — | acceptable | 特別な場所ですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0063 | pilot_train | N4 | おしゃれなカフェですね。 | — | acceptable | おしゃれなカフェですね。 | — | な형용사가 な를 사용해 명사를 수식합니다. | provisional |
| JT-0064 | pilot_train | N5 | 厚い本を選びました。 | — | acceptable | 厚い本を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0065 | pilot_train | N5 | 大きい傘を選びました。 | — | acceptable | 大きい傘を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0066 | pilot_train | N4 | 軽い鞄を選びました。 | — | acceptable | 軽い鞄を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0067 | pilot_train | N5 | 新しいスマホを選びました。 | — | acceptable | 新しいスマホを選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0068 | pilot_train | N5 | 温かいコーヒーを選びました。 | — | acceptable | 温かいコーヒーを選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0069 | pilot_train | N4 | 使いやすい筆記用具を選びました。 | — | acceptable | 使いやすい筆記用具を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0070 | pilot_train | N5 | 薄いノートを選びました。 | — | acceptable | 薄いノートを選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0071 | pilot_train | N5 | 安い服を選びました。 | — | acceptable | 安い服を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0072 | pilot_train | N5 | 高い時計を選びました。 | — | acceptable | 高い時計を選びました。 | — | い형용사가 그대로 명사를 수식합니다. | provisional |
| JT-0073 | pilot_train | N4 | 来週は公園に行くと思います。 | — | acceptable | 来週は公園に行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0074 | pilot_train | N5 | 来週は駅に行くと思います。 | — | acceptable | 来週は駅に行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0075 | pilot_train | N5 | 来週はスーパーに行くと思います。 | — | acceptable | 来週はスーパーに行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0076 | pilot_train | N4 | 来週は図書館に行くと思います。 | — | acceptable | 来週は図書館に行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0077 | pilot_train | N5 | 来週はカフェに行くと思います。 | — | acceptable | 来週はカフェに行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0078 | pilot_train | N5 | 来週は病院に行くと思います。 | — | acceptable | 来週は病院に行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0079 | pilot_train | N4 | 来週は学校に行くと思います。 | — | acceptable | 来週は学校に行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0080 | pilot_train | N5 | 来週はレストランに行くと思います。 | — | acceptable | 来週はレストランに行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0081 | pilot_train | N5 | 来週はコンビニに行くと思います。 | — | acceptable | 来週はコンビニに行くと思います。 | — | と思います 앞의 보통형이 적절합니다. | provisional |
| JT-0082 | pilot_train | N5 | 本、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 本、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0083 | pilot_train | N4 | 傘、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 傘、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0084 | pilot_train | N5 | 鞄、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 鞄、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0085 | pilot_train | N5 | スマホ、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | スマホ、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0086 | pilot_train | N4 | コーヒー、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | コーヒー、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0087 | pilot_train | N5 | 筆記用具、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 筆記用具、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0088 | pilot_train | N5 | ノート、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | ノート、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0089 | pilot_train | N4 | 服、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 服、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0090 | pilot_train | N5 | 時計、もう持ってきたよ。 | 친구에게 준비물을 가져왔다고 말합니다. | acceptable | 時計、もう持ってきたよ。 | — | 회화에서 목적격 조사를 생략할 수 있습니다. | provisional |
| JT-0091 | pilot_train | N5 | 今は何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 今は何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0092 | pilot_train | N5 | そこで何してる？ | 친한 사이의 일상 대화입니다. | acceptable | そこで何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0093 | pilot_train | N4 | 今日は何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 今日は何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0094 | pilot_train | N5 | 先生、何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 先生、何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0095 | pilot_train | N5 | 駅で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 駅で何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0096 | pilot_train | N4 | 一人で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 一人で何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0097 | pilot_train | N5 | 朝から何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 朝から何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0098 | pilot_train | N5 | まだ何してる？ | 친한 사이의 일상 대화입니다. | acceptable | まだ何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0099 | pilot_train | N4 | 外で何してる？ | 친한 사이의 일상 대화입니다. | acceptable | 外で何してる？ | — | している의 회화 축약형 してる를 허용합니다. | provisional |
| JT-0100 | pilot_dev | N5 | あのう、今夜は公園に行きます。 | — | acceptable | あのう、今夜は公園に行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0101 | pilot_dev | N5 | ええと、今夜は駅に行きます。 | — | acceptable | ええと、今夜は駅に行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0102 | pilot_dev | N5 | そうですね、今夜はスーパーに行きます。 | — | acceptable | そうですね、今夜はスーパーに行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0103 | pilot_dev | N4 | ええ、今夜は図書館に行きます。 | — | acceptable | ええ、今夜は図書館に行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0104 | pilot_dev | N5 | あの、今夜はカフェに行きます。 | — | acceptable | あの、今夜はカフェに行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0105 | pilot_dev | N5 | その、今夜は病院に行きます。 | — | acceptable | その、今夜は病院に行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0106 | pilot_dev | N4 | うーん、今夜は学校に行きます。 | — | acceptable | うーん、今夜は学校に行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0107 | pilot_dev | N5 | まあ、今夜はレストランに行きます。 | — | acceptable | まあ、今夜はレストランに行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0108 | pilot_dev | N5 | えっと、今夜はコンビニに行きます。 | — | acceptable | えっと、今夜はコンビニに行きます。 | — | 완성된 문장 속 필러를 문법 오류로 보지 않습니다. | provisional |
| JT-0109 | pilot_dev | N4 | まだ終えていません。 | 숙제를 끝냈는지 물었습니다. | acceptable | まだ終えていません。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0110 | pilot_dev | N5 | 図書館です。 | 어디에서 공부하는지 물었습니다. | acceptable | 図書館です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0111 | pilot_dev | N5 | 三時です。 | 몇 시에 만나는지 물었습니다. | acceptable | 三時です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0112 | pilot_dev | N5 | 友達です。 | 함께 온 사람이 누구인지 물었습니다. | acceptable | 友達です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0113 | pilot_dev | N4 | 明日です。 | 출발일이 언제인지 물었습니다. | acceptable | 明日です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0114 | pilot_dev | N5 | はい、お願いします。 | 도움을 줄지 제안받았습니다. | acceptable | はい、お願いします。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0115 | pilot_dev | N5 | 二つです。 | 몇 개 필요한지 물었습니다. | acceptable | 二つです。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0116 | pilot_dev | N4 | 電車です。 | 무엇을 타고 왔는지 물었습니다. | acceptable | 電車です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0117 | pilot_dev | N5 | 大丈夫です。 | 도움이 필요한지 물었습니다. | acceptable | 大丈夫です。 | — | 주어진 질문에 대한 짧은 응답으로 성립합니다. | provisional |
| JT-0118 | pilot_train | N5 | 先週は公園に行きました。それから写真を撮った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は公園に行きました。それから写真を撮った。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0119 | pilot_train | N4 | 先週は駅に行きました。それから切符を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は駅に行きました。それから切符を買った。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0120 | pilot_train | N5 | 先週はスーパーに行きました。それから野菜を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はスーパーに行きました。それから野菜を買った。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0121 | pilot_train | N5 | 先週は図書館に行きました。それから本を借りた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は図書館に行きました。それから本を借りた。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0122 | pilot_train | N5 | 先週はカフェに行きました。それからコーヒーを飲んだ。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はカフェに行きました。それからコーヒーを飲んだ。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0123 | pilot_train | N4 | 先週は病院に行きました。それから薬をもらった。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は病院に行きました。それから薬をもらった。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0124 | pilot_train | N5 | 先週は学校に行きました。それから授業を受けた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週は学校に行きました。それから授業を受けた。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0125 | pilot_train | N5 | 先週はレストランに行きました。それから昼ご飯を食べた。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はレストランに行きました。それから昼ご飯を食べた。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0126 | pilot_train | N4 | 先週はコンビニに行きました。それから新聞を買った。 | 친구에게 지난 일을 말하며 문체 통일 요구는 없습니다. | acceptable | 先週はコンビニに行きました。それから新聞を買った。 | — | 각 문장이 문법적으로 성립하며 문체 전환만으로 교정하지 않습니다. | provisional |
| JT-0127 | pilot_train | N5 | この道なら、公園まで歩いて行けます。 | — | acceptable | この道なら、公園まで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0128 | pilot_train | N5 | この道なら、駅まで歩いて行けます。 | — | acceptable | この道なら、駅まで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0129 | pilot_train | N4 | この道なら、スーパーまで歩いて行けます。 | — | acceptable | この道なら、スーパーまで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0130 | pilot_train | N5 | この道なら、図書館まで歩いて行けます。 | — | acceptable | この道なら、図書館まで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0131 | pilot_train | N5 | この道なら、カフェまで歩いて行けます。 | — | acceptable | この道なら、カフェまで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0132 | pilot_train | N5 | この道なら、病院まで歩いて行けます。 | — | acceptable | この道なら、病院まで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0133 | pilot_train | N4 | この道なら、学校まで歩いて行けます。 | — | acceptable | この道なら、学校まで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0134 | pilot_train | N5 | この道なら、レストランまで歩いて行けます。 | — | acceptable | この道なら、レストランまで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0135 | pilot_train | N5 | この道なら、コンビニまで歩いて行けます。 | — | acceptable | この道なら、コンビニまで歩いて行けます。 | — | なら와 가능형 行けます의 연결이 적절합니다. | provisional |
| JT-0136 | pilot_dev | N4 | 明後日は公園を行きます。 | — | needs_correction | 明後日は公園に行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0137 | pilot_dev | N5 | 明後日は駅を行きます。 | — | needs_correction | 明後日は駅に行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0138 | pilot_dev | N5 | 明後日はスーパーを行きます。 | — | needs_correction | 明後日はスーパーに行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0139 | pilot_dev | N4 | 明後日は図書館を行きます。 | — | needs_correction | 明後日は図書館に行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0140 | pilot_dev | N5 | 明後日はカフェを行きます。 | — | needs_correction | 明後日はカフェに行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0141 | pilot_dev | N5 | 明後日は病院を行きます。 | — | needs_correction | 明後日は病院に行きます。 | particle_misuse | 목적지를 나타내는 조사로 고칩니다. | provisional |
| JT-0142 | pilot_train | N5 | 昨日は学校を本を買いました。 | — | needs_correction | 昨日は学校で本を買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0143 | pilot_train | N4 | 昨日は売店を傘を買いました。 | — | needs_correction | 昨日は売店で傘を買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0144 | pilot_train | N5 | 昨日はコンビニを飲み物を買いました。 | — | needs_correction | 昨日はコンビニで飲み物を買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0145 | pilot_train | N5 | 昨日は書店を雑誌を買いました。 | — | needs_correction | 昨日は書店で雑誌を買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0146 | pilot_train | N4 | 昨日は神社をお守りを買いました。 | — | needs_correction | 昨日は神社でお守りを買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0147 | pilot_train | N5 | 昨日は駅前を弁当を買いました。 | — | needs_correction | 昨日は駅前で弁当を買いました。 | particle_misuse | 구매가 일어난 장소에는 で를 사용합니다. | provisional |
| JT-0148 | pilot_train | N5 | 学校で図書室があります。 | — | needs_correction | 学校に図書室があります。 | particle_misuse | 존재 장소에는 に를 사용합니다. | provisional |
| JT-0149 | pilot_train | N4 | ホテルで荷物があります。 | — | needs_correction | ホテルに荷物があります。 | particle_misuse | 존재 장소에는 に를 사용합니다. | provisional |
| JT-0150 | pilot_train | N5 | 銀行でATMがあります。 | — | needs_correction | 銀行にATMがあります。 | particle_misuse | 존재 장소에는 に를 사용합니다. | provisional |
| JT-0151 | pilot_train | N5 | 会社で会議室があります。 | — | needs_correction | 会社に会議室があります。 | particle_misuse | 존재 장소에는 に를 사용합니다. | provisional |
| JT-0152 | pilot_train | N5 | 市役所で相談窓口があります。 | — | needs_correction | 市役所に相談窓口があります。 | particle_misuse | 존재 장소에는 に를 사용합니다. | provisional |
| JT-0153 | pilot_dev | N4 | 毎朝、手紙を書きくます。 | — | needs_correction | 毎朝、手紙を書きます。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0154 | pilot_dev | N5 | 週末に服を買うます。 | — | needs_correction | 週末に服を買います。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0155 | pilot_dev | N5 | 駅で友達を待つます。 | — | needs_correction | 駅で友達を待ちます。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0156 | pilot_dev | N4 | 先生の話を聞くます。 | — | needs_correction | 先生の話を聞きます。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0157 | pilot_dev | N5 | 日本語で話すます。 | — | needs_correction | 日本語で話します。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0158 | pilot_dev | N5 | 公園で遊ぶます。 | — | needs_correction | 公園で遊びます。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0159 | pilot_train | N4 | 昨日、手紙を書きくました。 | — | needs_correction | 昨日、手紙を書きました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0160 | pilot_train | N5 | 先週、服を買うました。 | — | needs_correction | 先週、服を買いました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0161 | pilot_train | N5 | 駅で友達を待つました。 | — | needs_correction | 駅で友達を待ちました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0162 | pilot_train | N5 | 先生の話を聞くました。 | — | needs_correction | 先生の話を聞きました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0163 | pilot_train | N4 | 日本語で話すました。 | — | needs_correction | 日本語で話しました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0164 | pilot_train | N5 | 公園で遊ぶました。 | — | needs_correction | 公園で遊びました。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0165 | pilot_train | N5 | この用紙に住所を書きてください。 | — | needs_correction | この用紙に住所を書いてください。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0166 | pilot_train | N4 | 少し待ちてください。 | — | needs_correction | 少し待ってください。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0167 | pilot_train | N5 | この本を読みてください。 | — | needs_correction | この本を読んでください。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0168 | pilot_train | N5 | もう一度話すてください。 | — | needs_correction | もう一度話してください。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0169 | pilot_train | N4 | 駅まで歩くてください。 | — | needs_correction | 駅まで歩いてください。 | verb_conjugation | 동사의 활용 형태를 문형에 맞게 고칩니다. | provisional |
| JT-0170 | pilot_dev | N5 | 昨日は寒いかったです。 | — | needs_correction | 昨日は寒かったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0171 | pilot_dev | N5 | 料理は美味しいかったです。 | — | needs_correction | 料理は美味しかったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0172 | pilot_dev | N5 | 鞄は重いかったです。 | — | needs_correction | 鞄は重かったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0173 | pilot_dev | N4 | 試験は難しいかったです。 | — | needs_correction | 試験は難しかったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0174 | pilot_dev | N5 | 旅行は楽しいかったです。 | — | needs_correction | 旅行は楽しかったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0175 | pilot_dev | N5 | 部屋は暑いかったです。 | — | needs_correction | 部屋は暑かったです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0176 | pilot_train | N4 | この時計は高いくないです。 | — | needs_correction | この時計は高くないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0177 | pilot_train | N5 | 道は長いくないです。 | — | needs_correction | 道は長くないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0178 | pilot_train | N5 | 今日は忙しいくないです。 | — | needs_correction | 今日は忙しくないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0179 | pilot_train | N4 | この服は安いくないです。 | — | needs_correction | この服は安くないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0180 | pilot_train | N5 | 荷物は大きいくないです。 | — | needs_correction | 荷物は大きくないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0181 | pilot_train | N5 | 駅は遠いくないです。 | — | needs_correction | 駅は遠くないです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0182 | pilot_train | N5 | この店は安いて便利です。 | — | needs_correction | この店は安くて便利です。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0183 | pilot_train | N4 | 今日は寒いて大変です。 | — | needs_correction | 今日は寒くて大変です。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0184 | pilot_train | N5 | 道は長いて暗いです。 | — | needs_correction | 道は長くて暗いです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0185 | pilot_train | N5 | 鞄は軽いて便利です。 | — | needs_correction | 鞄は軽くて便利です。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0186 | pilot_train | N4 | 料理は辛いて美味しいです。 | — | needs_correction | 料理は辛くて美味しいです。 | adjective_conjugation | い형용사의 활용을 문형에 맞게 고칩니다. | provisional |
| JT-0187 | pilot_dev | N5 | 今朝は寒いだです。 | — | needs_correction | 今朝は寒いです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0188 | pilot_dev | N5 | この鞄は大きいだです。 | — | needs_correction | この鞄は大きいです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0189 | pilot_dev | N4 | 料理は美味しいだです。 | — | needs_correction | 料理は美味しいです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0190 | pilot_dev | N5 | 駅は遠いだです。 | — | needs_correction | 駅は遠いです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0191 | pilot_dev | N5 | この服は安いだです。 | — | needs_correction | この服は安いです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0192 | pilot_dev | N5 | 道は長いだです。 | — | needs_correction | 道は長いです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0193 | pilot_train | N4 | この町は静かなです。 | — | needs_correction | この町は静かです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0194 | pilot_train | N5 | 先生は元気なです。 | — | needs_correction | 先生は元気です。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0195 | pilot_train | N5 | 問題は簡単なです。 | — | needs_correction | 問題は簡単です。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0196 | pilot_train | N4 | この店は有名なです。 | — | needs_correction | この店は有名です。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0197 | pilot_train | N5 | 説明は自然なです。 | — | needs_correction | 説明は自然です。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0198 | pilot_train | N5 | 今日は特別なです。 | — | needs_correction | 今日は特別です。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0199 | pilot_train | N4 | 私は旅行が好きだです。 | — | needs_correction | 私は旅行が好きです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0200 | pilot_train | N5 | 妹は音楽が好きだです。 | — | needs_correction | 妹は音楽が好きです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0201 | pilot_train | N5 | 友達は映画が好きだです。 | — | needs_correction | 友達は映画が好きです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0202 | pilot_train | N5 | 父は料理が好きだです。 | — | needs_correction | 父は料理が好きです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0203 | pilot_train | N4 | 先生は読書が好きだです。 | — | needs_correction | 先生は読書が好きです。 | copula_conjugation | 서술어의 정중 종결 형태를 올바르게 고칩니다. | provisional |
| JT-0204 | pilot_train | N5 | 静か町に住んでいます。 | — | needs_correction | 静かな町に住んでいます。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0205 | pilot_train | N5 | 有名店で食べました。 | — | needs_correction | 有名な店で食べました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0206 | pilot_train | N4 | 元気子どもが遊んでいます。 | — | needs_correction | 元気な子どもが遊んでいます。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0207 | pilot_train | N5 | 簡単問題を解きました。 | — | needs_correction | 簡単な問題を解きました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0208 | pilot_train | N5 | 特別日になりました。 | — | needs_correction | 特別な日になりました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0209 | pilot_train | N4 | 自然日本語を話します。 | — | needs_correction | 自然な日本語を話します。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0210 | pilot_train | N5 | 新しい安いな時計を買いました。 | — | needs_correction | 新しい安い時計を買いました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0211 | pilot_train | N5 | 大きいな鞄を持っています。 | — | needs_correction | 大きい鞄を持っています。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0212 | pilot_train | N5 | 美味しいな料理を食べました。 | — | needs_correction | 美味しい料理を食べました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0213 | pilot_train | N4 | 長いな道を歩きました。 | — | needs_correction | 長い道を歩きました。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0214 | pilot_train | N5 | 寒いな朝でした。 | — | needs_correction | 寒い朝でした。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0215 | pilot_train | N5 | 楽しいな旅行でした。 | — | needs_correction | 楽しい旅行でした。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0216 | pilot_train | N4 | これは先生を本です。 | — | needs_correction | これは先生の本です。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0217 | pilot_train | N5 | あれは友達を傘です。 | — | needs_correction | あれは友達の傘です。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0218 | pilot_train | N5 | これは父を時計です。 | — | needs_correction | これは父の時計です。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0219 | pilot_train | N4 | それは妹を鞄です。 | — | needs_correction | それは妹の鞄です。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0220 | pilot_train | N5 | これは店をカードです。 | — | needs_correction | これは店のカードです。 | modifier_connection | 명사를 수식하거나 연결하는 형태를 고칩니다. | provisional |
| JT-0221 | pilot_train | N5 | 昨日は図書館で勉強します。 | — | needs_correction | 昨日は図書館で勉強しました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0222 | pilot_train | N5 | 先週は東京へ行きます。 | — | needs_correction | 先週は東京へ行きました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0223 | pilot_train | N4 | 去年は日本語を習います。 | — | needs_correction | 去年は日本語を習いました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0224 | pilot_train | N5 | 一時間前に昼ご飯を食べます。 | — | needs_correction | 一時間前に昼ご飯を食べました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0225 | pilot_train | N5 | 昨夜は映画を見ます。 | — | needs_correction | 昨夜は映画を見ました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0226 | pilot_train | N4 | 二日前はホテルに泊まります。 | — | needs_correction | 二日前はホテルに泊まりました。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0227 | pilot_train | N5 | 明日は病院へ行きました。 | — | needs_correction | 明日は病院へ行きます。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0228 | pilot_train | N5 | 来週は試験を受けました。 | — | needs_correction | 来週は試験を受けます。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0229 | pilot_train | N4 | 来年は京都に住みました。 | — | needs_correction | 来年は京都に住みます。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0230 | pilot_train | N5 | 一時間後に出発しました。 | — | needs_correction | 一時間後に出発します。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0231 | pilot_train | N5 | 明日の夜は友達に会いました。 | — | needs_correction | 明日の夜は友達に会います。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0232 | pilot_train | N5 | 来月は新しい仕事を始めました。 | — | needs_correction | 来月は新しい仕事を始めます。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0233 | pilot_train | N4 | 旅行は明日始まりました。 | — | needs_correction | 旅行は明日始まります。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0234 | pilot_train | N5 | 会議は来週終わりました。 | — | needs_correction | 会議は来週終わります。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0235 | pilot_train | N5 | 工事は来年始まりました。 | — | needs_correction | 工事は来年始まります。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0236 | pilot_train | N4 | 説明会は一時間後に始まりました。 | — | needs_correction | 説明会は一時間後に始まります。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0237 | pilot_train | N5 | イベントは今夜始まりました。 | — | needs_correction | イベントは今夜始まります。 | tense_mismatch | 명시된 시간 표현과 서술어 시제를 일치시킵니다. | provisional |
| JT-0238 | pilot_train | N5 | 昨日は学校を本を読むました。 | — | needs_correction | 昨日は学校で本を読みました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0239 | pilot_train | N4 | 先週は図書館を新聞を読むました。 | — | needs_correction | 先週は図書館で新聞を読みました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0240 | pilot_train | N5 | 昨日は店を服を買うました。 | — | needs_correction | 昨日は店で服を買いました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0241 | pilot_train | N5 | 先週は公園を友達と話すました。 | — | needs_correction | 先週は公園で友達と話しました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0242 | pilot_train | N5 | 昨日は駅を先生を待つました。 | — | needs_correction | 昨日は駅で先生を待ちました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0243 | pilot_train | N4 | 先週はカフェを手紙を書くました。 | — | needs_correction | 先週はカフェで手紙を書きました。 | particle_misuse, verb_conjugation | 장소 조사와 동사 과거 활용을 각각 고칩니다. | provisional |
| JT-0244 | pilot_train | N5 | 白い小さいな犬が庭でいます。 | — | needs_correction | 白い小さい犬が庭にいます。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0245 | pilot_train | N5 | 大きいな鞄が部屋であります。 | — | needs_correction | 大きい鞄が部屋にあります。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0246 | pilot_train | N4 | 静か町で公園があります。 | — | needs_correction | 静かな町に公園があります。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0247 | pilot_train | N5 | 有名店で時計があります。 | — | needs_correction | 有名な店に時計があります。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0248 | pilot_train | N5 | 安いなホテルでカフェがあります。 | — | needs_correction | 安いホテルにカフェがあります。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0249 | pilot_train | N4 | 自然日本語の本が机であります。 | — | needs_correction | 自然な日本語の本が机にあります。 | modifier_connection, particle_misuse | 명사 수식과 존재 장소 조사를 모두 고칩니다. | provisional |
| JT-0250 | pilot_train | N5 | 昨日の料理は美味しいかったので、明日も食べました。 | — | needs_correction | 昨日の料理は美味しかったので、明日も食べます。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0251 | pilot_train | N5 | 昨日は寒いかったので、明日は家にいました。 | — | needs_correction | 昨日は寒かったので、明日は家にいます。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0252 | pilot_train | N5 | 先週は忙しいかったですが、来週は休みました。 | — | needs_correction | 先週は忙しかったですが、来週は休みます。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0253 | pilot_train | N4 | 昨日の鞄は重いかったので、明日は使いませんでした。 | — | needs_correction | 昨日の鞄は重かったので、明日は使いません。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0254 | pilot_train | N5 | 去年の旅行は楽しいかったので、来年も行きました。 | — | needs_correction | 去年の旅行は楽しかったので、来年も行きます。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0255 | pilot_train | N5 | 昨夜は暑いかったですが、明日は涼しかったです。 | — | needs_correction | 昨夜は暑かったですが、明日は涼しいです。 | adjective_conjugation, tense_mismatch | 형용사 활용과 시간에 맞지 않는 시제를 모두 고칩니다. | provisional |
| JT-0256 | pilot_train | N4 | （無言） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （無言） | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0257 | pilot_train | N5 | ［無音］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［無音］ | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0258 | pilot_train | N5 | ……（沈黙） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ……（沈黙） | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0259 | pilot_train | N4 | （返答なし） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （返答なし） | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0260 | pilot_train | N5 | ［発話なし］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［発話なし］ | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0261 | pilot_train | N5 | ……？ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ……？ | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0262 | pilot_train | N5 | （考え中） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （考え中） | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0263 | pilot_train | N4 | ［沈黙が続く］ | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | ［沈黙が続く］ | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0264 | pilot_train | N5 | （声なし） | 실제 일본어 발화가 기록되지 않았습니다. | insufficient_evidence | （声なし） | — | 판단할 일본어 발화 내용이 없습니다. | provisional |
| JT-0265 | pilot_train | N5 | えっと…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | えっと…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0266 | pilot_train | N4 | あのですね…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | あのですね…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0267 | pilot_train | N5 | うーん…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | うーん…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0268 | pilot_train | N5 | その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | その…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0269 | pilot_train | N4 | まあ…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | まあ…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0270 | pilot_train | N5 | ええと、その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | ええと、その…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0271 | pilot_train | N5 | あのう…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | あのう…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0272 | pilot_train | N5 | そうですね…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | そうですね…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0273 | pilot_train | N4 | ちょっと、その…… | 머뭇거림 뒤의 본문이 녹음되지 않았습니다. | insufficient_evidence | ちょっと、その…… | — | 필러만 있고 판단할 명제가 없습니다. | provisional |
| JT-0274 | pilot_dev | N5 | 今朝、駅で先生に | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 今朝、駅で先生に | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0275 | pilot_dev | N5 | 来週、友達と映画を | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 来週、友達と映画を | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0276 | pilot_dev | N4 | この料理を作ったのは | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | この料理を作ったのは | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0277 | pilot_dev | N5 | もし時間があったら | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | もし時間があったら | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0278 | pilot_dev | N5 | 昨日、病院から | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 昨日、病院から | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0279 | pilot_dev | N4 | 日本に来てからずっと | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 日本に来てからずっと | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0280 | pilot_dev | N5 | 私が一番好きなのは | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 私が一番好きなのは | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0281 | pilot_dev | N5 | 雨が降らなければ | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | 雨が降らなければ | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0282 | pilot_dev | N5 | その本を読んだあとで | 녹음이 문장 중간에서 종료되었습니다. | insufficient_evidence | その本を読んだあとで | — | 누락된 서술어나 절을 추측하지 않습니다. | provisional |
| JT-0283 | pilot_train | N4 | 今日は［音声欠落］です。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 今日は［音声欠落］です。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0284 | pilot_train | N5 | 明日は［判別不能］へ行きます。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 明日は［判別不能］へ行きます。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0285 | pilot_train | N5 | ［環境音のみ］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［環境音のみ］ | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0286 | pilot_train | N4 | 駅で［一部欠落］を買いました。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 駅で［一部欠落］を買いました。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0287 | pilot_train | N5 | 昨日は［音声なし］。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 昨日は［音声なし］。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0288 | pilot_train | N5 | ［録音失敗］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［録音失敗］ | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0289 | pilot_train | N4 | 先生が［聞き取り不能］と言いました。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | 先生が［聞き取り不能］と言いました。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0290 | pilot_train | N5 | この本は［雑音区間］です。 | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | この本は［雑音区間］です。 | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0291 | pilot_train | N5 | ［発話区間なし］ | 대괄호 부분의 원음과 대안 전사가 제공되지 않았습니다. | insufficient_evidence | ［発話区間なし］ | — | 누락되거나 식별할 수 없는 구간을 임의로 채우지 않습니다. | provisional |
| JT-0292 | pilot_train | N5 | I will visit the library tomorrow. | — | insufficient_evidence | I will visit the library tomorrow. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0293 | pilot_train | N4 | Please wait here for a moment. | — | insufficient_evidence | Please wait here for a moment. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0294 | pilot_train | N5 | My friend bought a new camera. | — | insufficient_evidence | My friend bought a new camera. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0295 | pilot_train | N5 | We studied Japanese last night. | — | insufficient_evidence | We studied Japanese last night. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0296 | pilot_train | N4 | 내일은 병원에 갈 예정입니다. | — | insufficient_evidence | 내일은 병원에 갈 예정입니다. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0297 | pilot_train | N5 | 친구와 도서관에서 공부했습니다. | — | insufficient_evidence | 친구와 도서관에서 공부했습니다. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0298 | pilot_train | N5 | 이 가방은 생각보다 무겁습니다. | — | insufficient_evidence | 이 가방은 생각보다 무겁습니다. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0299 | pilot_train | N4 | 다시 한번 천천히 말해주세요. | — | insufficient_evidence | 다시 한번 천천히 말해주세요. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
| JT-0300 | pilot_train | N5 | 오늘 저녁에는 집에서 쉽니다. | — | insufficient_evidence | 오늘 저녁에는 집에서 쉽니다. | — | 일본어 문법 판단 범위 밖의 입력이며 번역문을 정답으로 만들지 않습니다. | provisional |
