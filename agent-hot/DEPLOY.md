# AgentHot 发布

AgentHot 通过 [Build AgentHot](https://github.com/Harzva/AgenticResearchLab/actions/workflows/agent-hot.yml) 构建。相关文件变更时，PR 和分支推送会运行仓库测试并上传 agent-hot 静态产物。也可在工作流页面选择 Run workflow。生产站使用 main 分支成功运行的产物。

## 下载并核对构建产物

从工作流的成功运行详情取得运行 ID。在已经核验的部署暂存目录执行以下命令，把 RUN_ID 换成该次运行的数字 ID。需要 GitHub CLI、可登录个人阿里云的 aliyun-ts SSH 别名和本机的 shasum。

~~~bash
set -euo pipefail

repo=Harzva/AgenticResearchLab
run_id=RUN_ID
case "$run_id" in ''|*[!0-9]*) exit 1 ;; esac

revision=$(gh run view "$run_id" --repo "$repo" \
  --json conclusion,event,headBranch,headSha,workflowName \
  --jq 'select(.conclusion == "success" and .headBranch == "main" and .workflowName == "Build AgentHot" and (.event == "push" or .event == "workflow_dispatch")) | .headSha')
test "${#revision}" -eq 40
case "$revision" in *[!0-9a-f]*) exit 1 ;; esac

stage=$(mktemp -d "$PWD/agent-hot-release.XXXXXX")
gh run download "$run_id" --repo "$repo" --name agent-hot --dir "$stage/site"
test -s "$stage/site/index.html"
(
  cd "$stage/site"
  find . -type f -exec shasum -a 256 {} + | LC_ALL=C sort
) > "$stage/SHA256SUMS"
~~~

## 上传到个人阿里云

在同一终端执行下列命令。每次发布使用一个独立目录。校验通过后记录上一版位置，再切换 current。

~~~bash
base=/srv/harzva-agent-hot
release_id="$revision-$run_id"
release="$base/releases/$release_id"

ssh -o BatchMode=yes aliyun-ts \
  "set -eu; install -d -m 0755 '$base/releases'; mkdir -m 0755 '$release'; install -d -m 0755 '$release/agent-hot'"
tar -C "$stage/site" -cf - . | ssh -o BatchMode=yes aliyun-ts \
  "umask 022; tar --no-same-owner --no-same-permissions -xf - -C '$release/agent-hot'"
ssh -o BatchMode=yes aliyun-ts \
  "cd '$release/agent-hot' && sha256sum -c --quiet -" < "$stage/SHA256SUMS"
ssh -o BatchMode=yes aliyun-ts "runuser -u www-data -- test -r '$release/agent-hot/index.html'"

previous=$(ssh -o BatchMode=yes aliyun-ts "if test -L '$base/current'; then readlink -f '$base/current'; fi")
printf 'Previous release: %s\nNew release: %s\n' "$previous" "$release"
ssh -o BatchMode=yes aliyun-ts \
  "set -eu; ln -s '$release' '$base/.current-$release_id'; mv -Tf '$base/.current-$release_id' '$base/current'"
~~~

## 首次接入 HTTPS

创建服务端文件 /etc/nginx/snippets/harzva-agent-hot.locations.conf，内容如下。

~~~nginx
location = /agent-hot {
    auth_basic off;
    return 308 /agent-hot/;
}

location ^~ /agent-hot/ {
    auth_basic off;
    root /srv/harzva-agent-hot/current;
    index index.html;
    try_files $uri $uri/ =404;
    charset utf-8;
    charset_types text/plain text/markdown application/json application/javascript application/rss+xml;
    types {
        text/html html;
        text/css css;
        application/javascript js;
        application/json json;
        text/plain txt;
        application/rss+xml xml;
        text/markdown md;
    }
    gzip on;
    gzip_vary on;
    gzip_types application/json application/javascript text/css text/plain text/markdown application/rss+xml;

    add_header Access-Control-Allow-Origin "*" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options SAMEORIGIN always;
}

location ^~ /agent-hot/daily/ {
    auth_basic off;
    root /srv/harzva-agent-hot/live;
    if ($uri !~ "^/agent-hot/daily/(index\.json|latest\.json|rss\.xml|[0-9]{4}-[0-9]{2}-[0-9]{2}\.(?:json|md))$") {
        return 404;
    }
    try_files $uri =404;
    charset utf-8;
    charset_types application/json application/rss+xml text/markdown;
    types {
        application/json json;
        application/rss+xml xml;
        text/markdown md;
    }
    gzip on;
    gzip_vary on;
    gzip_types application/json application/rss+xml text/markdown;

    add_header Access-Control-Allow-Origin "*" always;
    add_header Cache-Control "no-cache" always;
    add_header X-Content-Type-Options nosniff always;
}
~~~

在 /etc/nginx/conf.d/harzva-interview.conf 的 harzva.online HTTPS server 中，与现有作品集 include 同级加入以下一行。保存变更前记录原配置摘要，并保留站点文件的副本。

~~~nginx
include /etc/nginx/snippets/harzva-agent-hot.locations.conf;
~~~

从个人阿里云运行 nginx -t，通过后运行 systemctl reload nginx。后续更新沿用同一配置，通过切换 current 发布。

## 启用每日专题

同一次成功运行会上传独立的 agent-hot-daily-runtime 产物。把它下载到部署暂存目录。服务代码和 systemd 文件位于站点的静态根之外。

~~~bash
gh run download "$run_id" --repo "$repo" --name agent-hot-daily-runtime --dir "$stage/runtime"
runtime="$base/bin/releases/$release_id"
ssh -o BatchMode=yes aliyun-ts "set -eu; install -d -m 0755 '$base/bin/releases'; mkdir -m 0755 '$runtime'"
tar -C "$stage/runtime" -cf - . | ssh -o BatchMode=yes aliyun-ts \
  "umask 022; tar --no-same-owner --no-same-permissions -xf - -C '$runtime'"
ssh -o BatchMode=yes aliyun-ts \
  "set -eu; test -r '$runtime/daily.py'; test -r '$runtime/build.py'; ln -s '$runtime' '$base/bin/.current-$release_id'; mv -Tf '$base/bin/.current-$release_id' '$base/bin/current'"
~~~

在个人阿里云创建专用服务账号和可写目录，再安装两份单元。服务读取已发布的 feed.json，只能在 daily 目录写入。Nginx 只提供日期文档、索引和订阅文件。

~~~bash
base=/srv/harzva-agent-hot
getent group agenthot-daily >/dev/null || groupadd --system agenthot-daily
id -u agenthot-daily >/dev/null 2>&1 || useradd --system --gid agenthot-daily \
  --no-create-home --shell /usr/sbin/nologin agenthot-daily
install -d -m 0755 "$base/live/agent-hot"
install -d -m 0755 -o agenthot-daily -g agenthot-daily "$base/live/agent-hot/daily"
install -m 0644 "$base/bin/current/systemd/agenthot-daily.service" /etc/systemd/system/
install -m 0644 "$base/bin/current/systemd/agenthot-daily.timer" /etc/systemd/system/
systemd-analyze calendar '*-*-* 14:00:00 Asia/Shanghai'
systemctl daemon-reload
systemctl start agenthot-daily.service
systemctl enable --now agenthot-daily.timer
systemctl list-timers agenthot-daily.timer
~~~

定时器每天北京时间 14:00 运行，错过触发后会补运行。当天重复执行时会复用已写入的专题。生产请求读取 arXiv cs.AI 的 Atom 源，允许最多 65 秒并协商压缩，最多选取首批 24 条完整的 Agent 相关论文作为候选。连接中断时，已完整读取至少 5 条候选即可继续核对来源日期。没有可用新文献时会生成精选回顾，并在 JSON 中标记 `mode: "review"`。首次运行结果见服务日志和公开的 daily/latest.json。运维人员可用 `--promote-review` 重试当天回顾，只有确实取得新文献时才更新同一个日期页。

## 验收

~~~bash
site=https://harzva.online
curl -fsS "$site/agent-hot/" -o "$stage/live-index.html"
cmp "$stage/site/index.html" "$stage/live-index.html"
test "$(curl -sS -o /dev/null -w '%{http_code}' "$site/agent-hot")" = 308
test "$(curl -sS -o /dev/null -w '%{http_code}' "$site/agent-hot/nonexistent-release-probe")" = 404
curl -fsS --compressed "$site/agent-hot/feed.json" -o "$stage/live-feed.json"
cmp "$stage/site/feed.json" "$stage/live-feed.json"
curl -fsS "$site/agent-hot/rss.xml" -o "$stage/live-rss.xml"
cmp "$stage/site/rss.xml" "$stage/live-rss.xml"
curl -fsSI "$site/agent-hot/llms.txt" >/dev/null
day=$(curl -fsS "$site/agent-hot/daily/latest.json" | jq -er '.date')
curl -fsSI "$site/agent-hot/daily/$day.json" >/dev/null
curl -fsSI "$site/agent-hot/daily/$day.md" >/dev/null
curl -fsSI "$site/agent-hot/daily/rss.xml" >/dev/null
test "$(curl -sS -o /dev/null -w '%{http_code}' "$site/agent-hot/daily/.publish.lock")" = 404
curl -fsSI "$site/agent-papers/" >/dev/null
curl -fsSI "$site/portfolio/" >/dev/null
~~~

在浏览器打开 AgentHot，抽查首页、分阶段条目和单条详情。确认 RSS 指向正式站点，llms.txt 中的条目 Markdown 可匿名读取。抽查来源链接和公开 PDF。

## 回滚

- **首次接入**时，从 HTTPS server 撤销本次新增的 include，检查 nginx -t，再 reload。确认 AgentHot 恢复为 404，作品集和 Agent 论文知识库仍返回 200。
- **后续更新**时，先确认发布时记录的上一版目录仍在且有 agent-hot/index.html。将临时链接指向上一版，再用 mv -Tf 替换 current。按同样的验收步骤核对上一版页面。
- **每日服务**需要回滚时，停用定时器，检查 oneshot 服务已经退出，再切回上一版 bin/current 并按需恢复对应的单元。每日已发布文档位于 live/agent-hot/daily，可以保留。

## 本地校验

从仓库根目录运行 `python3 agent-hot/build.py --out OUT`，将 OUT 换成新的或空的输出目录。成功后应看到 `feed.json`、`rss.xml`、`llms.txt` 和每个条目的 Markdown。构建允许公开 HTTPS 来源链接和 PDF 地址，静态产物只包含网页、索引和条目文档。

- `2026-11-20` 和 `2026-11-20T08:20:00+08:00` 是有效日期。日期必须真实，时间戳必须包含时区。
- 内网 IP、内网域名、非 HTTPS 和携带 token 的来源会被拒绝。构建只做离线格式校验，来源是否在线以发布前抽查为准。
- 条目 ID 用于地址和 RSS GUID。修订标题或说明时沿用原 ID。重复 ID、标题、同条目中的来源 URL 或未知来源类型会阻止构建。

每日专题可用 `python3 agent-hot/daily.py --feed OUT/feed.json --out DAILY_OUT --date 2026-11-20 --fixture FIXTURE` 离线复验。FIXTURE 可为 arXiv Atom XML，或包含 title、url、published_at、abstract 及可选 pdf_url 的 JSON 数组。空数组会走回顾分支。生产运行省略 --fixture 和 --date。
