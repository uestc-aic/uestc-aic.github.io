# AI 芯动力 · UESTC AIC

社团官网 UI 初版。原生 HTML、CSS、JavaScript，无需构建。

## 查看页面

打开 `dist/index.html` 即可查看。完整预览建议使用本地静态服务器。

## 内容与交互

- 自适应首页，包含社团介绍、活动预告、项目方向、资源库、组织架构、拟合作伙伴和招新入口。
- 活动分类、资源分类与搜索、详情弹窗、移动端导航、投稿格式复制。
- 六份可直接访问的公开学习资源。
- 芯片插画和标识为页面内 SVG，无需图片服务。
- 首期沙龙处于筹备阶段，候选主题、时间和地点均按当前信息展示。
- 报名表、QQ 群和投稿表单暂未接入；页面明确显示“待公布”，不收集报名数据。

## 修改入口

编辑 `dist/app.js` 顶部的 `CONFIG`：

```js
const CONFIG = {
  github: 'https://github.com/uestc-aic',
  recruitmentForm: '',       // 招新报名表的 HTTPS 地址
  qqGroup: '',               // QQ 群邀请的 HTTPS 地址
  contributionForm: '',      // 投稿表的 HTTPS 地址
  salonRegistration: '',     // 首期沙龙报名表的 HTTPS 地址
  salonTime: '期中后，具体时间待公布',
  salonLocation: '待公布'
};
```

填入相应地址后，弹窗自动显示可用入口。首页活动卡片的日期、地点位于 `dist/index.html`，正式确定后需同步修改。

资源数据在 `dist/app.js` 的 `RESOURCES` 中；页面文案和布局在 `dist/index.html`，颜色与响应式样式在 `dist/style.css`。

中文名暂用项目名称“AI 芯动力”，英文账号为 UESTC AIC。拟合作伙伴仅作筹备信息展示，请在合作确认后更新状态。

## 部署到 GitHub Pages

已附 `.github/workflows/pages.yml`，将 `dist` 发布到 GitHub Pages。该流程需要仓库主分支为 `main`。

1. 使用 GitHub CLI 的浏览器授权登录 `uestc-aic` 账号：`gh auth login`。
2. 在项目根目录初始化 Git，并创建或连接目标仓库。账号首页建议使用仓库名 `uestc-aic.github.io`。
3. 上传 `dist`、`.github` 和本说明。无需上传 `.openai` 或任何本地预览文件。
4. 在仓库 Settings → Pages 中，将 Source 设置为 GitHub Actions。
5. 推送至 `main` 后，等待 Deploy website to GitHub Pages 工作流成功。

账号首页在部署成功后通常对应 `https://uestc-aic.github.io/`。部署状态请以 GitHub 仓库 Actions 中的工作流结果为准。

页面字体按顺序使用 Google Fonts、系统中文字体与系统无衬线字体；外部字体加载失败时，中文内容和全部功能仍可使用。

## 参考

- https://uestc-ia.github.io/ ：参考社团介绍与开源社区入口的组织方式。
- http://teamup.20050917.xyz/ ：本次无法读取，未使用其内容。
- 用户提供的组织架构图与 GitHub 账号截图。
