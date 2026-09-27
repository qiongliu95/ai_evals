# IFEval Dataset Summary

Source: https://github.com/google-research/google-research/tree/e6890f85757dd84e27ca6df2dd30651dafad28e0/instruction_following_eval

Samples: **541**; instructions: **834**; types: **25**.
Fields: instruction_id_list, key, kwargs, prompt.
Single instruction: **305**; multi-instruction: **236**.

Counts below are instruction occurrences (not prompt counts).

| Instruction type | Count |
|---|---:|
| change_case:capital_word_frequency | 25 |
| change_case:english_capital | 25 |
| change_case:english_lowercase | 39 |
| combination:repeat_prompt | 41 |
| combination:two_responses | 24 |
| detectable_content:number_placeholders | 27 |
| detectable_content:postscript | 26 |
| detectable_format:constrained_response | 10 |
| detectable_format:json_format | 17 |
| detectable_format:multiple_sections | 14 |
| detectable_format:number_bullet_lists | 31 |
| detectable_format:number_highlighted_sections | 48 |
| detectable_format:title | 37 |
| keywords:existence | 39 |
| keywords:forbidden_words | 49 |
| keywords:frequency | 42 |
| keywords:letter_frequency | 33 |
| language:response_language | 31 |
| length_constraints:nth_paragraph_first_word | 12 |
| length_constraints:number_paragraphs | 27 |
| length_constraints:number_sentences | 52 |
| length_constraints:number_words | 52 |
| punctuation:no_comma | 66 |
| startend:end_checker | 26 |
| startend:quotation | 41 |

| Instructions per prompt | Prompts |
|---:|---:|
| 1 | 305 |
| 2 | 179 |
| 3 | 57 |

SHA256: `67ffeee0fcb87c317c5b08a2de85557b4a7e96ada6178aa645b4954fe4b53d49`

Original JSONL bytes and fields are retained. Per-prompt counts: `ifeval_prompt_inventory.csv`.
