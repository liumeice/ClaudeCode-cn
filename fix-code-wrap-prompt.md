# 修复任务：PDF 中代码块"提前换行"问题

## 你的任务

本项目是把 Claude Code 文档站（英文版）抓取并转为 PDF 的流水线（step1 抓侧边栏 → step2 逐页生成 PDF → step3 合并）。step2 脚本中的 `DOM_MANIPULATE_JS`（注入页面的 DOM 处理 + 打印 CSS）存在一个 bug：**生成的 PDF 里，代码块的长行会在明显放得下的位置提前折行**（约提前 19 个等宽字符）。请按下文的根因与修复方案修改 step2 脚本并验证。

典型症状（hooks 文档页）：JSON 示例中的这一行在 PDF 里被折成两行——

```
"command":
"${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh",
```

而按页面可用宽度（约 720px）本应完整放下（该行实测仅需约 619px）。

## 根因（已在中文版项目实测确认，两层）

**第一层：站点为"横向滚动"设计预留的右内边距。**
文档站的代码块组件是横向滚动组件（网页上长行靠滚动查看，不折行）。其样式表中存在这样一条规则（选择器可能略有出入，以 `[data-has-floating-buttons]` 为关键字定位）：

```css
[data-has-floating-buttons] > [data-component-part="code-block-root"] {
  padding-right: var(--code-padding-right, 0px) !important;  /* 实测解析为约 163px，为浮动按钮（复制按钮等）预留 */
}
```

同时内层 `<code>` 元素（shiki 高亮结构为 `pre > code > span.line`）有 `width: max-content; min-width: 100%`。流水线注入的打印 CSS 是：

```css
pre, code { white-space: pre-wrap !important; overflow-wrap: anywhere !important; max-width: 100% !important; }
```

`white-space: pre-wrap` 让长行折行（必要——PDF 无法滚动）；`max-width: 100%` 把 code 盒子收缩到 pre 宽度（如 720px）；**但上面那条 163px 右内边距原封不动残留在盒内（border-box）**，实际折行宽度变成 720 − 163 ≈ 557px——所有超过 557px 的行提前约 19 个字符折断。

**第二层（关键陷阱）：站点监听 `beforeprint` 重建代码块 DOM。**
Chromium 的 `page.pdf()` 渲染前会触发 `beforeprint` 事件，站点的代码块组件会在此时**重建 pre/code 的 DOM**。因此：

- 任何写在 `pre code` 元素上的**行内样式修复**（包括行内 `!important`、行内覆盖 `--code-padding-right` 变量）都会在渲染前被清掉，全部无效；
- 甚至注入 pre 内部的测试元素也会在 PDF 中凭空消失；
- 实时布局（包括 `page.emulate_media('print')` 模拟）看起来一切正常，只有真实 `page.pdf()` 产物才暴露问题——不要被模拟结果迷惑。

**正确做法：直接改写样式表规则本身（CSSOM）**——把那条 `padding-right: var(...)` 规则原地替换为字面 `0px !important`。样式表不会被 `beforeprint` 重建，DOM 无论怎么重建，规则恒生效。打印时浮动按钮本来就已被隐藏，该预留空间毫无用处，清零是安全的。

## 修复代码

在 step2 脚本的 `DOM_MANIPULATE_JS` 中、**注入打印 CSS（`pre, code { ... }` 那段 style 元素）之前**，加入（编号顺延你现有的步骤，命名为 10c 或类似）：

```js
// 10c. 修复代码块提前换行（必须在注入 print CSS 之前执行）。
//      详见注释说明：站点代码块为横向滚动设计，规则
//      [data-has-floating-buttons] > [data-component-part=...] {
//        padding-right: var(--code-padding-right, 0px) !important  (~163px)
//      }
//      在 max-width:100% 收缩后残留盒内，偷走折行宽度；且站点监听 beforeprint
//      重建代码块 DOM，行内修复会被清掉——因此改写样式表规则本身（CSSOM）。
(function() {
  function patchRules(rules) {
    for (var ri = 0; ri < rules.length; ri++) {
      var rule = rules[ri];
      if (rule.cssRules && !(rule instanceof CSSStyleRule)) {
        patchRules(rule.cssRules);
        continue;
      }
      if (!rule.selectorText) continue;
      if (rule.selectorText.indexOf('[data-has-floating-buttons]') >= 0 &&
          rule.style && rule.style.getPropertyValue('padding-right')) {
        rule.style.setProperty('padding-right', '0px', 'important');
      }
    }
  }
  for (var si = 0; si < document.styleSheets.length; si++) {
    var rules;
    try { rules = document.styleSheets[si].cssRules; } catch (e) { continue; }
    patchRules(rules);
  }
})();
```

注意：
- 若项目同时有单线程版和多线程版（`_mt`）两个 step2 脚本且共享同一段 `DOM_MANIPULATE_JS` 字符串，**两个文件都要改，改完程序化比对两段字符串逐字节一致**；
- 该 JS 在 `page.goto()` 完成后执行，此时样式表已加载，能遍历到目标规则；
- 若选择器已变（站点改版），用同样的遍历逻辑先 dump 所有含 `[data-has-floating-buttons]` 或对 `pre code` 设置 padding/width 的规则，确认后再改。

## 验证方法（必须实测，不能只看模拟）

1. 单独生成一个代码密集页面的测试 PDF（如 hooks 页面），从 step2 导入 `DOM_MANIPULATE_JS`、正常流程 apply 后 `page.pdf()` 输出；
2. 用 PyMuPDF 提取文本，检查原先折断的长行是否为完整单行，例如：

```python
import fitz
doc = fitz.open('test_hooks.pdf')
full = ''.join(p.get_text() for p in doc)
# 该行必须整体出现在某一页文本中：
ok = '"command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh",' in full
```

3. 检查无溢出（所有文本右缘 ≤ 页宽）：

```python
maxx = 0
for pno in range(len(doc)):
    for blk in doc[pno].get_text('dict')['blocks']:
        if blk.get('type') != 0: continue
        for line in blk['lines']:
            for span in line['spans']:
                maxx = max(maxx, span['bbox'][2])
print(maxx, doc[0].rect.width)  # maxx 必须小于页宽
```

4. 注意：仍会有**真正超宽的行**（超过整列宽度）在空格/连字符处折行，这是 `pre-wrap` 的正常行为，不算 bug；正文段落里的 `${CLAUDE...}` 出现在行首也是正文自然换行，与代码块无关。判定标准是"明显放得下却折了"的行是否恢复完整。
5. 修复后整本 PDF 页数通常会略微减少（代码块更紧凑），属预期。
