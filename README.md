# 岸上 · 广东高校招聘库

已预装 2026-10-09 核对的 174 条真实岗位，17 所院校，广州 / 深圳 / 佛山 / 东莞 / 惠州 / 中山 / 珠海 / 肇庆八市。公告和岗位表来自高校官网、广东省人社厅官网；保留正文、附件链接、发布日和证据文件。旧公告保留原发布日期，未披露字段保持待核实。

推荐使用交付包内的 Windows / macOS 启动文件。详细步骤见 [先读使用说明](delivery/先读使用说明.md)，来源与测试结果见 [过程与验证](delivery/过程与验证.md)。无需 Render、GitHub、服务器或付费 API。

## 浏览器版与自动更新

已提供无须安装的 GitHub Pages 浏览器版与每四小时尝试检查官方来源的工作流。个人档案、收藏、备注仅存浏览器，不上传。部署状态及账号首次启用步骤见 [浏览器版发布说明](PUBLIC_DEPLOYMENT.md)。表格及详情包含报名方式、所需材料和官方入口；未知内容待核实。定时任务可能延迟，源站访问失败会保留错误和旧数据。

## 本地启动

安装 Python 3.12 或更新版本。Windows 双击 `启动招聘库-Windows.bat`；macOS 双击 `启动招聘库-macOS.command`。首次会建立虚拟环境、安装公告与附件解析组件，然后打开本机浏览器。

Linux / 开发环境：

```bash
cd /workspace/Hanah-box
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --init
.venv/bin/python scripts/launch.py
```

默认仅监听本机，不公开个人资料。数据位于 `.data/library.sqlite`；首次预装真实快照，重复启动不会覆盖编辑、收藏或备考记录。运行时每天生成一次 SQLite 备份。停止程序后复制整个文件夹是完整备份方式。

## 自动采集与准确性

- 保持电脑联网、程序运行；每 4 小时检查配置栏目。停机期间不采集，重新启动后对超过 4 小时未检查的来源补查。页面可点击“立即检查”。
- 当前成功核对的入口为广外、深大人事招聘栏目及省人社厅高校公告。省人社厅入口限定已配置院校，排除附属医院、中小学、录用公示和考试通知。
- 支持正文岗位、岗位表的 XLS / XLSX / Excel 2003 XML；显式合并单元格展开，不推测缺失条件。PDF 提供文字提取函数，扫描 PDF、验证码和未识别表头保留为待核验，不绕过网站限制。
- 新增记录标为“自动整理待核验”；人工确认后可编辑标为“已核验”。已核对快照标为“原文已核对”。公告正文或同链接岗位附件字节变化会提示复核，保留旧核验时间。访问失败保留已有记录并显示原因。
- 多校区院校按院校所在地筛选；详情说明实际工作校区是否指定。滚动岗位人数为原表名额，剩余空缺须联系学校确认。长期公告保留原发布日期，不保证当前仍有名额。
- 本版覆盖有限，并非广东全省完整目录。尚无学校所有招聘系统、公众号或登录后内容的全面采集。

## 备考使用

表格支持省、市、区县、类别、学历、编制、状态及关键词 / 专业筛选。默认显示正在 / 即将报名、滚动招聘和截止待核实；勾选“包含已截止岗位”查看历史要求。支持官方原文、岗位附件、收藏、报名进度、私人备注和 Excel 导出。

在线 / 邮件岗位建议截止前 3 天，需提前审核前 5 天；邮寄按寄出 / 送达规则及物流天数计算，材料更早期限优先。短报名窗口建议开放后尽快提交；滚动岗位建议尽快，未知截止不编造日期。仅日期的官方截止不虚构时刻。全部日期按北京时间处理。

条件匹配仅根据已录入证据；年龄计算日、应届身份和专业近似均须核实。提醒在页面内显示，没有邮件、微信或系统推送。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python app.py --check
```

37 项规则、来源解析和认证测试。浏览器验证需要开发用 Playwright 与 Chromium（用户运行不需要），在测试临时数据库中进行，不写入真实个人库：

```bash
python tests/browser_smoke.py
python tests/offline_smoke.py
python tests/real_content_smoke.py
```

独立网页由 `.venv/bin/python scripts/build_offline.py` 生成。`dist/hanah-recruitment-real.html` 是带真实数据的可编辑快照，保存在该浏览器内，需定期下载 JSON 备份；自动采集使用本地运行版。受管测试浏览器限制 file://，独立文件验证在本地 HTTP 下完成。

## 开发与来源证据

`collector.py`：官方网页与岗位表解析。`app.py`：SQLite、采集计划、接口、备份。`sources.json`：官方栏目。`data/verified_snapshot.json`：核对快照。`research/`：官方网页、岗位表和采集日志。`web/`：前端与独立版适配器。

接口包括 `/api/state`、`/api/jobs`、`/api/personal`、`/api/profile`、`/api/refresh`、`/api/export`。后台编辑验证官方 HTTPS 来源域名。个人库与虚拟环境均被 Git 忽略；交付包不含个人数据库。

保留的 `render.yaml` / `DEPLOY.md` 为先前托管方案资料，本次交付和验证采用本地个人版。

个人版使用 private/profile.json 首次导入个人档案；private/ 已加入 Git 忽略。生成私人交付包使用 `.venv/bin/python scripts/package_delivery.py --personal`，通用包排除私人文件。个人版单文件网页为 dist/hanah-WYH-editable.html。
