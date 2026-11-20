# Agent 论文知识库发布

知识库通过 [Build knowledge base](https://github.com/Harzva/AgenticResearchLab/actions/workflows/knowledge-base.yml) 构建。相关文件变更时，PR 和分支推送会运行仓库测试并上传 agent-papers 静态产物。也可在工作流页面选择 Run workflow。生产站使用 main 分支成功运行的产物。

## 下载并核对构建产物

从工作流的成功运行详情取得运行 ID。在已经核验的部署暂存目录执行以下命令，把 RUN_ID 换成该次运行的数字 ID。需要 GitHub CLI、可登录个人阿里云的 aliyun-ts SSH 别名和本机的 shasum。

~~~bash
set -euo pipefail

repo=Harzva/AgenticResearchLab
run_id=RUN_ID
case "$run_id" in ''|*[!0-9]*) exit 1 ;; esac

revision=$(gh run view "$run_id" --repo "$repo" \
  --json conclusion,event,headBranch,headSha,workflowName \
  --jq 'select(.conclusion == "success" and .headBranch == "main" and .workflowName == "Build knowledge base" and (.event == "push" or .event == "workflow_dispatch")) | .headSha')
test "${#revision}" -eq 40
case "$revision" in *[!0-9a-f]*) exit 1 ;; esac

stage=$(mktemp -d "$PWD/agent-papers-release.XXXXXX")
gh run download "$run_id" --repo "$repo" --name agent-papers --dir "$stage/site"
test -s "$stage/site/index.html"
(
  cd "$stage/site"
  find . -type f -exec shasum -a 256 {} + | LC_ALL=C sort
) > "$stage/SHA256SUMS"
~~~

## 上传到个人阿里云

在同一终端执行下列命令。每次发布使用一个独立目录。校验通过后记录上一版位置，再切换 current。

~~~bash
base=/srv/harzva-agent-papers
release_id="$revision-$run_id"
release="$base/releases/$release_id"

ssh -o BatchMode=yes aliyun-ts \
  "set -eu; install -d -m 0755 '$base/releases'; mkdir -m 0755 '$release'; install -d -m 0755 '$release/agent-papers'"
tar -C "$stage/site" -cf - . | ssh -o BatchMode=yes aliyun-ts \
  "umask 022; tar --no-same-owner --no-same-permissions -xf - -C '$release/agent-papers'"
ssh -o BatchMode=yes aliyun-ts \
  "cd '$release/agent-papers' && sha256sum -c --quiet -" < "$stage/SHA256SUMS"
ssh -o BatchMode=yes aliyun-ts "runuser -u www-data -- test -r '$release/agent-papers/index.html'"

previous=$(ssh -o BatchMode=yes aliyun-ts "if test -L '$base/current'; then readlink -f '$base/current'; fi")
printf 'Previous release: %s\nNew release: %s\n' "$previous" "$release"
ssh -o BatchMode=yes aliyun-ts \
  "set -eu; ln -s '$release' '$base/.current-$release_id'; mv -Tf '$base/.current-$release_id' '$base/current'"
~~~

## 首次接入 HTTPS

创建服务端文件 /etc/nginx/snippets/harzva-agent-papers.locations.conf，内容如下。

~~~nginx
location = /agent-papers {
    auth_basic off;
    return 308 /agent-papers/;
}

location ^~ /agent-papers/ {
    auth_basic off;
    root /srv/harzva-agent-papers/current;
    index index.html;
    try_files $uri $uri/ =404;
    charset utf-8;
    charset_types text/plain text/csv text/markdown application/json application/javascript;
    types {
        text/html html;
        text/css css;
        application/javascript js;
        application/json json;
        text/plain txt;
        text/csv csv;
        text/markdown md;
    }
    gzip on;
    gzip_vary on;
    gzip_types application/json application/javascript text/css text/plain text/csv text/markdown;

    add_header Access-Control-Allow-Origin "*" always;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options SAMEORIGIN always;
}
~~~

在 /etc/nginx/conf.d/harzva-interview.conf 的 harzva.online HTTPS server 中，与现有作品集 include 同级加入以下一行。保存变更前记录原配置摘要，并保留站点文件的副本。

~~~nginx
include /etc/nginx/snippets/harzva-agent-papers.locations.conf;
~~~

从个人阿里云运行 nginx -t，通过后运行 systemctl reload nginx。后续更新沿用同一配置，通过切换 current 发布。

## 验收

~~~bash
site=https://harzva.online
curl -fsS "$site/agent-papers/" -o "$stage/live-index.html"
cmp "$stage/site/index.html" "$stage/live-index.html"
test "$(curl -sS -o /dev/null -w '%{http_code}' "$site/agent-papers")" = 308
test "$(curl -sS -o /dev/null -w '%{http_code}' "$site/agent-papers/nonexistent-release-probe")" = 404
curl -fsSI "$site/agent-papers/catalog.json" >/dev/null
curl -fsSI "$site/portfolio/" >/dev/null
~~~

在浏览器打开知识库，确认列表、搜索、论文详情和图谱能正常使用。抽查已公开 PDF 链接能到达论文来源。

## 回滚

- **首次接入**时，从 HTTPS server 撤销本次新增的 include，检查 nginx -t，再 reload。确认知识库恢复为 404，作品集仍返回 200。
- **后续更新**时，先确认发布时记录的上一版目录仍在且有 agent-papers/index.html。将临时链接指向上一版，再用 mv -Tf 替换 current。按同样的验收步骤核对上一版页面。
