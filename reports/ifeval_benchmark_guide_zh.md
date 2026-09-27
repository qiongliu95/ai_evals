# IFEval Benchmark 理解材料

本文只解释当前工作区已固定的 Google IFEval 数据与官方 scorer，不涉及 DeepSeek、Qwen 或任何模型答案。数据来自 `input_data.jsonl`，共 541 条 prompt；scorer 来自 Google Research 固定提交 `e6890f85757dd84e27ca6df2dd30651dafad28e0`。

## 1. 全部 25 种 instruction type

表中的“样本数”指至少包含一次该 instruction id 的不同 prompt 数量；“约束实例数”指它在 `instruction_id_list` 中的实际出现次数。同一 prompt 可以用同一 id 两次表示一个范围，因此两列不一定相同。每类示例选自官方数据中相对较短的一条真实 prompt，未改写原文。

| Instruction id | 中文解释 | 样本数 | 约束实例数 | 真实样本示例 |
|---|---|---:|---:|---|
| `change_case:capital_word_frequency` | 全大写单词的数量需满足给定下界或严格上界。 | 20 | 25 | key 2820 — “Write a serious riddle about trips and stitches in a poem style that includes at least 15 words in all capital letters.” |
| `change_case:english_capital` | 整个回复须被检测为英语，且所有有大小写之分的字母均为大写。 | 25 | 25 | key 2247 — “Write an essay about Alvin and the Chipmunks in English and in all capital letters.” |
| `change_case:english_lowercase` | 整个回复须被检测为英语，且不得出现大写字母。 | 39 | 39 | key 1593 — “Compose a poem all in lowercase letters about my friend Barnet.” |
| `combination:repeat_prompt` | 回复开头须逐字重复指定的原请求；官方检查器实际检查忽略大小写后的 `startswith`。 | 41 | 41 | key 3563 — “What is the name of the actor who played Gandalf in Lord of the Rings?<br>First repeat the question above without change of words, then give your answer.” |
| `combination:two_responses` | 给出两个不同且非空的回答，并用恰好六个星号 `******` 分隔。 | 24 | 24 | key 3263 — “Is \"jiang\" a Chinese name? What are other names similar to \"jiang\"? Separate your two answers with ******” |
| `detectable_content:number_placeholders` | 至少包含指定数量的方括号占位符，如 `[address]`。 | 27 | 27 | key 3126 — “Write an article named \"How to conduct a job interview\". Include at least one placeholder, such as [question].” |
| `detectable_content:postscript` | 回复末尾区域须出现以指定标记开头的附言，如 `P.S.` 或 `P.P.S`。 | 26 | 26 | key 2396 — “Write me a poem about a long lasting war. Add a postscript at the end starting with P.P.S” |
| `detectable_format:constrained_response` | 整个回复须严格等于预定义的三个短句之一：`My answer is yes.`、`My answer is no.` 或 `My answer is maybe.`。 | 10 | 10 | key 3753 — “If a + b + c = 30 and b = 10 and c = 5. Is a = 20? Answer ”My answer is yes.\" or \"My answer is no.\" or \"My answer is maybe.\"” |
| `detectable_format:json_format` | 整个回复去除首尾空白及可选 Markdown code fence 后，必须能被 JSON parser 解析。 | 17 | 17 | key 3223 — “List all facts about Lionel Messi in a structured output. In particular, Format your entire output in JSON.” |
| `detectable_format:multiple_sections` | 至少包含指定数量的编号 section，并用指定词加数字标记，如 `SECTION 1`。 | 14 | 14 | key 2925 — “Write a joke about anarchists in Tulsa in 3 sections. Mark the beginning of each section with SECTION X.” |
| `detectable_format:number_bullet_lists` | 恰好包含指定数量、以 `*` 或 `-` 开头的 Markdown bullet 行。 | 31 | 31 | key 2314 — “Name exactly 3 names for a black and white dog using markdown bullet points such as:<br>* Bullet point 1” |
| `detectable_format:number_highlighted_sections` | 至少包含指定数量的 Markdown 星号强调片段。 | 48 | 48 | key 1886 — “Write a riddle for the word \"façade\" that contains at least 3 italic text phrases in markdown syntax, i.e *italic text*.” |
| `detectable_format:title` | 至少包含一个非空、用双尖括号包裹的标题，如 `<<title>>`。 | 37 | 37 | key 3057 — “Please write a riddle about the inverse function with a title wrapped in double angular brackets, i.e. <<title>>.” |
| `keywords:existence` | 指定的每个关键词都须出现；检查时忽略大小写。 | 39 | 39 | key 2662 — “Write a tweet for the president of the United States. The tweet should include the keywords \"engages\" and \"lightly\".” |
| `keywords:forbidden_words` | 指定词均不得作为完整单词出现；检查时忽略大小写。 | 49 | 49 | key 2811 — “Can you write a rap that doesn't include the keywords \"Yo\", \"check\", and \"peace\"?” |
| `keywords:frequency` | 指定字符串的出现次数需满足给定下界或严格上界；检查时忽略大小写。 | 39 | 42 | key 3091 — “Write a quiz about bits that includes the word elephant at least 3 times.” |
| `keywords:letter_frequency` | 指定字符的出现次数需满足给定下界或严格上界；检查时忽略大小写。 | 33 | 33 | key 3478 — “Write a song about Layton, making sure to use the letter \"a\" at most once.” |
| `language:response_language` | 整个回复应被 `langdetect` 判定为指定 ISO 639-1 语言。 | 31 | 31 | key 2299 — “Write a lame joke about engagements in entirely Swahili, no other language is allowed.” |
| `length_constraints:nth_paragraph_first_word` | 回复须有恰好指定数量、以两个换行分隔的段落，并要求第 N 段以指定单词开头。 | 12 | 12 | key 3073 — “How are you doing today? Could you write me exactly 4 paragraphs each separated by two new lines? Please start the first paragraph with the word \"firms\".” |
| `length_constraints:number_paragraphs` | 用 Markdown 分隔符 `***` 划分后，须得到恰好指定数量的非空段落。 | 27 | 27 | key 2467 — “Write a rap about an abyss in exactly 4 paragraphs. Separate paragraphs with the markdown divider: ***.” |
| `length_constraints:number_sentences` | 用 NLTK 句子切分后，句数需满足给定下界或严格上界；范围通常由两个同名约束共同表达。 | 46 | 52 | key 1837 — “Write a song about miniatures that contains 20 to 25 sentences. Do not forget to add punctuations.” |
| `length_constraints:number_words` | 用官方 tokenizer 计数后，词数需满足给定下界或严格上界。 | 50 | 52 | key 1092 — “Write a short blog post about a trip to Japan using less than 300 words.” |
| `punctuation:no_comma` | 整个回复不得含英文半角逗号 `,`。 | 66 | 66 | key 3615 — “Write a riddle about Camilla that doesn't use commas.” |
| `startend:end_checker` | 去除首尾空白和外层双引号后，回复必须以指定短语结尾；比较忽略大小写。 | 26 | 26 | key 2398 — “Give me a poem about California. The very end of your entire response should read exactly like: your love, and thanks.” |
| `startend:quotation` | 去除首尾空白后，整个回复的第一个和最后一个字符都必须是英文双引号。 | 40 | 41 | key 219 — “Do you think Kareena Kapoor is a good actor? Wrap your response with double quotation marks.” |

这里的“at most N”通常编码为 `relation: "less than"`、阈值 `N+1`。例如 key 3478 的“字母 a 最多一次”对应 `let_frequency: 2`，检查逻辑是实际次数 `< 2`。

## 2. 辅助理解分组

以下分组只为了阅读方便，不改变、合并或重命名任何官方 instruction id。同一约束从不同角度也可能被放到其他类别，下面采用最直观的主用途。

### A. 词汇与字符内容

- `keywords:existence`
- `keywords:forbidden_words`
- `keywords:frequency`
- `keywords:letter_frequency`
- `change_case:capital_word_frequency`

这组检查“必须出现什么、不能出现什么、出现多少次”。它们大多是正则或字符计数，因此衡量的是可检测的表面约束，不判断文本内容是否正确。

### B. 语言、大小写与标点

- `language:response_language`
- `change_case:english_capital`
- `change_case:english_lowercase`
- `punctuation:no_comma`

这组约束作用于整个回复的书写方式。语言依赖统计检测器；大小写类同时要求英语检测通过。

### C. 长度与计数

- `length_constraints:number_words`
- `length_constraints:number_sentences`
- `length_constraints:number_paragraphs`
- `length_constraints:nth_paragraph_first_word`

这组通过 tokenizer、句子切分或明确分隔符计数。一个区间经常拆成两个 instruction 实例，例如“20 到 25 句”表示为 `>= 20` 和 `< 26`。

### D. 可检测格式与结构

- `detectable_format:json_format`
- `detectable_format:number_bullet_lists`
- `detectable_format:number_highlighted_sections`
- `detectable_format:multiple_sections`
- `detectable_format:title`
- `detectable_format:constrained_response`

这组要求特定的机器可识别外形，如 JSON、列表、强调、标题、编号 section 或限定短答。

### E. 边界、附加内容与包裹方式

- `detectable_content:number_placeholders`
- `detectable_content:postscript`
- `startend:end_checker`
- `startend:quotation`

这组关注回复中特定位置或包裹形式：模板占位符、末尾附言、精确结束语、首尾引号。

### F. 复合回答流程

- `combination:repeat_prompt`
- `combination:two_responses`

这组规定回答过程或组合方式：先复述请求再回答，或输出两个不同回答并使用固定分隔符。

## 3. 五个完整真实样本

### 3.1 单 instruction：key 3615

**Prompt**

> Write a riddle about Camilla that doesn't use commas.

**instruction_id_list**

```json
["punctuation:no_comma"]
```

**kwargs**

```json
[{}]
```

**实际要求**

- `punctuation:no_comma`：完整回复中不得出现英文半角逗号 `,`。主题是否确实是 Camilla 的谜语，不在这个 checker 的自动判定范围内。

### 3.2 单 instruction：key 3223

**Prompt**

> List all facts about Lionel Messi in a structured output. In particular, Format your entire output in JSON.

**instruction_id_list**

```json
["detectable_format:json_format"]
```

**kwargs**

```json
[{}]
```

**实际要求**

- `detectable_format:json_format`：去除首尾空白，并允许去掉外层的 `````json`` / `````Json`` / `````JSON`` / ````` `` code fence 后，剩余文本必须能被 `json.loads` 解析。checker 不验证其中是否真的列全了 Lionel Messi 的事实，也不验证事实真实性。

### 3.3 Multi-instruction：key 1837

**Prompt**

> Write a song about miniatures that contains 20 to 25 sentences. Do not forget to add punctuations.

**instruction_id_list**

```json
[
  "length_constraints:number_sentences",
  "length_constraints:number_sentences"
]
```

**kwargs**

```json
[
  {"relation": "at least", "num_sentences": 20},
  {"relation": "less than", "num_sentences": 26}
]
```

**每个 constraint 的实际要求**

1. 第一个 `length_constraints:number_sentences`：NLTK 切分结果至少为 20 句。
2. 第二个 `length_constraints:number_sentences`：NLTK 切分结果严格少于 26 句。

两者同时通过才表示 20–25 句。这个样本也说明：一个 prompt 可以重复同一个 instruction id，每次使用不同 kwargs；instruction-level 统计会把它们视为两个约束实例。

### 3.4 Multi-instruction：key 1107

**Prompt**

> Write two jokes about rockets. Do not contain commas in your response. Separate the two jokes with 6 asterisk symbols: ******.

**instruction_id_list**

```json
[
  "punctuation:no_comma",
  "combination:two_responses"
]
```

**kwargs**

```json
[
  {},
  {}
]
```

**每个 constraint 的实际要求**

1. `punctuation:no_comma`：完整回复不得出现英文半角逗号。
2. `combination:two_responses`：以 `******` 切分后须恰好有两个不同的非空回答；两端多出的空段可被忽略，中间空段不允许。

两项都通过，prompt-level 才通过。checker 不自动判断两个回答是否都真的是关于火箭的笑话。

### 3.5 Multi-instruction：key 1000

**Prompt**

> Write a 300+ word summary of the wikipedia page "https://en.wikipedia.org/wiki/Raymond_III,_Count_of_Tripoli". Do not use any commas and highlight at least 3 sections that has titles in markdown format, for example *highlighted section part 1*, *highlighted section part 2*, *highlighted section part 3*.

**instruction_id_list**

```json
[
  "punctuation:no_comma",
  "detectable_format:number_highlighted_sections",
  "length_constraints:number_words"
]
```

**kwargs**

```json
[
  {},
  {"num_highlights": 3},
  {"relation": "at least", "num_words": 300}
]
```

**每个 constraint 的实际要求**

1. `punctuation:no_comma`：不得出现英文半角逗号。
2. `detectable_format:number_highlighted_sections`：至少检测到 3 个由 Markdown 星号包裹的非空片段。
3. `length_constraints:number_words`：官方 tokenizer 计数至少 300 词。

三项均通过才算 prompt-level pass。官方 scorer 不检查摘要是否忠实于链接内容，因此这个样本的自动分数只代表可检测约束遵循情况。

## 4. 官方 scorer 如何形成分数

### 4.1 Strict 与 loose 的共同基础

对每条 prompt，官方 scorer 依次遍历 `instruction_id_list`：

1. 用 instruction id 从 registry 找到 checker class；
2. 用同一位置的 `kwargs` 构造规则；
3. 调用 `check_following(response)`；
4. 形成一个与 `instruction_id_list` 等长的布尔列表 `follow_instruction_list`；
5. 对该列表执行 `all(...)`，形成 `follow_all_instructions`。

空回复无论 checker 本身如何判断，strict 和 loose 都记为失败。

### 4.2 Strict

Strict 只把原始回复完整地交给每个 checker，不删除或改写任何字符。因此，额外的开场语、结尾说明、Markdown 装饰等都属于被评分文本。

### 4.3 Loose

Loose 为同一原始回复构造 8 个候选版本：

1. 原文；
2. 删除全部 `*` 的原文；
3. 删除第一行；
4. 删除最后一行；
5. 同时删除第一行和最后一行；
6. 删除第一行后，再删除全部 `*`；
7. 删除最后一行后，再删除全部 `*`；
8. 删除第一、最后一行后，再删除全部 `*`。

每个 instruction 只要在任一非空候选上通过，就得到 loose pass。原文也是候选之一，所以某条 instruction strict pass 时，它也必然 loose pass。

### 4.4 三个真实样本中的评分含义

#### 样本 key 3615：`punctuation:no_comma`

- strict：在完整回复中搜索英文逗号；找不到才通过。
- loose：依次检查 8 个候选。若逗号只出现在可删除的第一行或最后一行，strict 会失败，而删掉该行的候选可能通过 loose。
- 该样本只有一个 instruction，所以这一条 instruction 的布尔值与该 prompt 的 pass/fail 相同。

#### 样本 key 3223：`detectable_format:json_format`

- strict：完整回复在处理可选 code fence 后必须是合法 JSON。若 JSON 前后还有普通说明文本，解析通常失败。
- loose：若额外说明恰好独占第一行或最后一行，移除相应行后可能只剩合法 JSON，于是 loose 通过。
- 删除星号也可能消除 Markdown 装饰造成的干扰，但 JSON checker 本身已特别允许常见的三反引号 code fence。

#### 样本 key 1107：`punctuation:no_comma` + `combination:two_responses`

- strict 会得到两个 instruction 结果，例如概念上的 `[no_comma_pass, two_responses_pass]`。
- strict prompt-level 只有在两个值都是 `true` 时通过。
- loose 对两个 instruction 分别遍历 8 个候选。六星分隔符在原文候选中仍存在，因此 `two_responses` 可以在那里通过；如果某个逗号只在首行或末行，`no_comma` 可以在另一个删行候选中通过。
- 因而 loose 的两个 instruction 甚至可能由不同候选文本分别满足。官方实现随后对两个 loose 布尔值做 `all(...)`；它不要求存在同一个候选同时满足全部约束。这是解释 loose prompt-level 时需要保留的一个重要细节。

### 4.5 Instruction-level 与 prompt-level

对某一评测集合，四个常见指标可写成：

```text
instruction-level strict
= strict 通过的 instruction 实例数 / 全部 instruction 实例数

instruction-level loose
= loose 通过的 instruction 实例数 / 全部 instruction 实例数

prompt-level strict
= 所有 instruction 都 strict 通过的 prompt 数 / prompt 总数

prompt-level loose
= 所有 instruction 都 loose 通过的 prompt 数 / prompt 总数
```

Instruction-level 是约束实例的微平均。key 1837 中两个同名的句数约束会分别进入分子/分母；只通过一个时，该样本贡献 1 个 pass 和 1 个 fail，但 prompt-level 仍是 fail。Prompt-level 更严格，因为 multi-instruction 样本必须全部约束通过。

### 4.6 Strict / loose 产生差异的典型情况

- 回复正文符合约束，但首行带有礼貌开场、标签或解释，删首行后通过。
- 回复正文符合约束，但末行带有补充说明，删末行后通过。
- Markdown 星号使某些文本检查失败，删除全部星号后通过。
- multi-instruction prompt 的不同约束在不同 loose 候选上分别通过，最终 prompt-level loose 仍可能通过。

Loose 是官方定义的“较宽松上界”，不是对语义正确性的二次判断，也不是由模型或 LLM judge 评分。

## 5. 阅读 scorer 时应知道的边界

- Scorer 只检查 registry 中定义的可验证约束，不评价事实正确性、相关性、文风质量或任务主体是否完成。
- `language:response_language` 依赖 `langdetect`；官方代码在无法检测语言时返回通过，这可能影响很短的文本。
- `keywords:frequency` 使用正则查找指定字符串，不保证一定按完整词边界计数。
- `keywords:letter_frequency` 的 checker 只正式接受英文字母 `a`–`z`。当前数据中 key 1122 使用 `#`、key 1129 使用 `!`；官方实现会把这类字符替换为随机英文字母。这两条在正式报告中应单独复核，并固定随机种子以保证重评分一致。
- 星号同时承担 Markdown 强调、bullet、段落分隔和六星分隔符等多种角色；loose 的“删除全部星号”变体可能影响这些格式 checker。不过原文候选仍保留，所以 loose 不会把 strict pass 反转成 fail。
- `number_highlighted_sections` 的正则实现与人对 Markdown 的理解不一定完全一致；分析失败案例时应查看逐 instruction 结果和原始输出。

## 理解 IFEval 后，正式跑模型前还需要确认哪些事项

1. **实验对象**：确认 provider 账户中实际可调用的模型 ID、API 返回的实际 model/version、地域 endpoint 与权限；不要仅依赖模型别名。
2. **统一推理设置**：确认是否保持单条 user message、无额外 system prompt、非思考模式、`temperature=0`、`max_tokens=4096`，以及两个 provider 的参数是否具有可比含义。
3. **样本范围与预算**：先定义 smoke test 的 sample id，再决定是否执行 541 条全量；根据输入/输出上限估算费用，不把验证脚本或失败重试算成新实验而不记录。
4. **外部信息策略**：部分 prompt 引用网页或要求事实内容。需明确模型是否只凭内部知识回答、是否禁用联网工具，并在报告中说明 IFEval scorer 不验证事实质量。
5. **数据与 scorer 版本**：固定当前数据 SHA256、Google commit、Python 依赖和 NLTK 资源；固定所有涉及随机 fallback 的种子。
6. **异常与统计分母**：预先约定 runtime error、grader error、空输出、内容过滤和未完成样本如何报告；不得把这些静默当作模型 fail 或从分母中无说明地删除。
7. **截断策略**：明确 `finish_reason=length` 是否仍按原文评分、是否另列 truncated 数量，以及是否允许以更高 token 上限重跑。
8. **重试与可重复性**：定义超时、限流和中断后的重试规则；记录 attempt，避免把“第一次失败后成功”的样本与一次完成的样本混为一谈。即使 temperature 为 0，云端结果也未必完全确定。
9. **已知 scorer 边界**：正式跑前决定如何标记并人工复核 key 1122、1129 的非字母字符约束、语言检测异常、Markdown 星号相关判定和 strict/loose 分歧案例。官方主分数可以保留，但这些问题应进入 Evaluation Quality Review。
10. **结果解释口径**：提前声明四个指标只衡量可自动检测的 instruction following；模型能力结论还需要人工检查任务完成度、事实质量、歧义和 scorer false positive/false negative。

