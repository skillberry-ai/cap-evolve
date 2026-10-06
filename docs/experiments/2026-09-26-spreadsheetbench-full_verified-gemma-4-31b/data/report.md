## Full_verified suite — spreadsheetbench  (held-out test split)

Agent `rits/google/gemma-4-31B-it` · optimizer Claude Code `aws/claude-opus-5` · 8 iteration(s) · base→opt is the seed vs the best candidate on the **same 280 SEALED test tasks**, which the optimizer never saw (selection happened on a disjoint val split). This is a held-out generalization number.

| bench | task | reward (base→opt) | Δ | note |
|---|---|---|---|:--:|
| spreadsheetbench | `17-35` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `22-47` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `23-24` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `24-23` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `41-47` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `51-12` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `60-7` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `262-17` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `263-1` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `267-18` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `269-43` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `269-44` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `279-23` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `290-1` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `333-29` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `384-4` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `408-5` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `433-47` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `469-9` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `472-15` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `477-45` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `493-18` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `547-18` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `66-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `73-45` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `80-42` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `82-30` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `82-38` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `84-40` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `91-34` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `97-36` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `105-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `109-21` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `118-50` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `130-9` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `142-19` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `146-49` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `147-48` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `156-14` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `157-4` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `165-23` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `177-6` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `191-40` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `203-15` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `230-16` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `236-22` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `250-20` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `108-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `120-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `141-20` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `142-12` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `183-8` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `192-22` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `209-30` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `227-40` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `302-1` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `334-11` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `341-14` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `353-6` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `359-21` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `367-23` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `370-43` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `374-18` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `374-31` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `382-29` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `387-16` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `395-36` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `398-14` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `399-14` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `402-43` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `408-39` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `409-45` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `414-20` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `416-15` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `416-27` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `440-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `448-11` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `463-17` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `486-17` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `488-14` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `493-5` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `496-15` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `496-34` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `510-3` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `516-46` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `524-31` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `531-18` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `534-26` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `545-35` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `547-43` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `560-12` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `577-40` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `585-41` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `599-9` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `15380` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `30930` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `37900` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `38462` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `38703` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `38823` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `38969` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `39046` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `39432` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `39667` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `40478` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `41410` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `41691` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `42526` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `44389` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `45635` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `45896` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `46167` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `46240` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `47798` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `47842` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `48080` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `48257` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `48365` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `48643` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `48745` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `48982` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `49196` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `49237` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `49300` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `49333` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `50088` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `50768` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `50796` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `50916` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `51090` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `51262` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `51289` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `51431` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `52216` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52575` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `54144` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54196` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `54242` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54590` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `54675` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `1563` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `1818` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `1925` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `2768` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `3002` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `3911` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `4714` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `6239` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `6698` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `7902` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `8942` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `9111` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `9391` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `9448` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `9569` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `9726` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `10452` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `11276` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `13284` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `14240` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `15387` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `15671` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `16511` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `17111` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `18935` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `31628` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `31915` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32023` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `32093` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `32255` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32293` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32337` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32438` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32562` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `32612` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `33157` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `34210` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `35739` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `35742` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `35747` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `36191` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `36764` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `37086` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `37229` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `37378` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `37462` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `37554` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `36277` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `37456` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `39190` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `40757` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `40892` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `40959` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `41348` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42181` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42216` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `42515` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42930` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `43436` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `43589` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `44266` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `44296` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `44628` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `45063` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `45372` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `45738` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `46121` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `46897` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `49857` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `50250` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `50521` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `50631` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `50683` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `50971` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `51354` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `51556` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `51680` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `52050` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `52220` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `52233` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52305` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52541` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `52964` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `53117` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `53161` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `53383` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `53994` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `54085` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54274` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54474` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54513` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54667` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `54717` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54925` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55049` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `55060` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55085` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55427` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `55965` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55979` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `56274` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `56378` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `56419` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `56599` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `56921` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57033` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57113` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57232` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `58484` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `58701` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `58723` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `58949` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `59196` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42902` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `43657` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `44017` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `45707` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `45937` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55260` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55421` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `55708` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55977` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `56786` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `57117` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57262` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `57354` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `57558` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57612` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `57989` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `58032` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `58499` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `58687` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `58904` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `59129` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `59224` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `59358` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `59511` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `59794` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `59884` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `59902` | 1.000 → 1.000 | +0.000 |  |

**Suite (held-out):** mean reward 0.632 → 0.764 (Δ +0.132 (+21% rel)) · best = `r3_decide` · optimizer $57.85 over 8 iter(s)

### Iterations

| phase | iter | candidate | accepted | reward | optimizer $ | optimizer time | eval $ | eval time |
|---|:--:|---|:--:|---|---|---|---|---|
| baseline | — | `seed` | — | 0.625 | $0.0000 | 0s | $0.0000 | 34m05s |
| iterate | 1 | `r1_contract` | ✅ | 0.775 | $0.0000 | — | $0.0000 | 15m04s |
| iterate | 2 | `r2_numeric` | ❌ | 0.846 | $0.0000 | — | $0.0000 | 31m48s |
| iterate | 3 | `r3_decide` | ✅ | 0.887 | $0.0000 | — | $0.0000 | 33m22s |
| iterate | 4 | `r4_silent` | ❌ | 0.842 | $0.0000 | — | $0.0000 | 132m51s |
| iterate | 5 | `r5_verdict` | ❌ | 0.800 | $0.0000 | — | $0.0000 | 42m55s |
| iterate | 6 | `r6_scope` | ❌ | 0.769 | $0.0000 | — | $0.0000 | 28m17s |
| iterate | 7 | `r7_path` | ❌ | 0.846 | $0.0000 | — | $0.0000 | 30m56s |
| iterate | 8 | `r8_cut` | ❌ | 0.875 | $0.0000 | — | $0.0000 | 41m35s |
| finalize | — | `r3_decide` | — | 0.764 | $0.0000 | 0s | $0.0000 | 103m29s |
| finalize_baseline | — | `seed` | — | 0.632 | $0.0000 | 0s | $0.0000 | 128m48s |
| unattributed | — | `(whole run)` | — | — | $57.8454 | 1039m30s | $0.0000 | — |

**Totals:** optimizer $57.8454 over 1039m30s · eval $0.0000 over 623m09s

> The `unattributed` row is metered spend no phase above owns (optimizer $57.8454 — agent mode runs ONE optimizer process, metered whole-loop, so no round owns a share of it). It is shown rather than dropped so these totals match what the run actually paid: `spent` reads $0.00 runner + $57.85 optimizer.
