# 本番デプロイ手順書（運用前チェックリスト）

Web画面（Next.js）・API サーバー（FastAPI）・Neo4j を本番運用する際の、リバースプロキシ設置・
TLS・レート制限・`.env` 設定の手引き。**このファイルに実際の秘密情報（APIキー等）を書かないこと。**
値はサーバ上の `.env`（gitignore 済み）にのみ置く。

関連: [`../ADVANCED_USAGE.md`](../ADVANCED_USAGE.md)（構成の概要）、[`PRIVACY_GUIDELINES.md`](PRIVACY_GUIDELINES.md)（外部AIとデータの扱い）。

> **まず確認**: 本システムは**1台のパソコン内で完結する運用（LAN 内・localhost のみ）が既定**です。
> インターネットに公開する必要が本当にあるかを先に検討してください。公開しないなら、この手順書の
> プロキシ設定は不要で、[`QUICK_START.md`](QUICK_START.md) の起動手順だけで足ります。

---

## 全体構成

```
             インターネット（HTTPS）
                     │
          ┌──────────▼────────────────┐
          │  リバースプロキシ           │  ← TLS 終端 / アクセス制御 / レート制限
          │  (Caddy 推奨 / nginx)      │
          └───┬────────────────┬──────┘
      /api/*  │                │  それ以外
   127.0.0.1  ▼                ▼  127.0.0.1
        :8001 ┌────────────┐   ┌────────────┐ :3001
              │  API       │   │  Web画面    │
              │ (FastAPI)  │   │ (Next.js)  │
              └─────┬──────┘   └────────────┘
                    ▼
                 Neo4j :7687 / 7474
```

**設計上の要点**

- **API サーバーにはアプリ内の認証機構がありません。** 外部公開する場合、アクセス制御は
  **必ず前段（プロキシの Basic 認証・IP 制限・VPN・社内ネットワーク限定など）で行う**こと。
  認証なしでインターネットに晒すと、要配慮個人情報が誰でも読める状態になります。
- API（8001）と Web画面（3001）は **`127.0.0.1` にバインド**し、外部公開は必ずプロキシ経由にする。
- **同一ホスト名で `/api/*` を API に、それ以外を Web画面に振り分ける**構成を推奨。ブラウザから
  API を直接呼ぶ設計のため、同一オリジンにしておけば CORS 設定が不要になる。
- Neo4j（7687 / 7474）は**絶対に外部公開しない**。プロキシの背後にも置かず、localhost のみ。
- **Claude Desktop（MCP）からの登録・照会は、Neo4j が動いているパソコン上でのみ行える。**
  `mcp-neo4j-cypher` は `localhost:7687` に接続するため、サーバー運用にした場合、
  職員の手元のパソコンの Claude Desktop からはつながらない（7687 は公開しないのが前提）。
  登録作業はサーバー機上で行うか、1台完結の既定構成のまま運用すること。
- **登録を行うときは、Neo4j だけでなく API サーバー（port 8001）も起動しておくこと。**
  書き込み前の検証（`POST /api/graph/validate`）と重複検査（`POST /api/dedup/check`）は
  API 側の機能で、止まっていると機械検査なしの登録になる。

---

## 1. `.env` チェックリスト

サーバ上の `.env`（プロジェクトルート）に設定する。`.env.example` をコピーして埋める。

| 変数 | 必須 | 本番の推奨値 | 備考 |
|------|:---:|------|------|
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` | ✅ | 実接続情報 | **パスワードは既定の `password` から必ず変更する**。 |
| `BACKEND_PORT` | ー | `8001` | API サーバーのポート。 |
| `FRONTEND_PORT` | ー | `3001` | Web画面のポート。 |
| `PSEUDONYMIZATION_ENABLED` | ー | 用途次第 | 研修・デモで匿名化するとき true。Python 経路のみ有効。 |

> **AI キーの設定は不要になりました**: AI を Claude 一本にまとめたため（2026-08）、`.env` に
> AI 関連のキー（GEMINI_API_KEY 等）を書く欄はありません。Claude との接続は Claude Desktop の
> MCP 設定で行います。データの扱いは [`PRIVACY_GUIDELINES.md`](PRIVACY_GUIDELINES.md) 2.2 を参照。

Web画面側は、ブラウザから API を呼ぶための公開 URL をビルド時に埋め込む必要がある。

```bash
# frontend/.env.production （公開ドメインに置き換える）
NEXT_PUBLIC_API_URL=https://example.org
```

未設定だと `http://localhost:8001` を見に行くため、他端末のブラウザからは動作しない。

**投入後の確認**: `curl -s http://127.0.0.1:8001/api/health` が `{"status":"ok"}` を返すこと。

---

## 2A. Caddy（推奨・自動 TLS）

Let's Encrypt による証明書自動取得・更新が標準で付く。レート制限は
[`caddy-ratelimit`](https://github.com/mholt/caddy-ratelimit) プラグインを組み込んだ
バイナリが必要（`xcaddy build --with github.com/mholt/caddy-ratelimit`）。

`Caddyfile` の例（`example.org` は実ドメインに置換）:

```caddyfile
{
    # レート制限プラグイン利用時のみ有効化
    order rate_limit before reverse_proxy
}

example.org {
    encode gzip

    # アプリ側に認証がないため、前段で必ずアクセス制御をかける。
    # ハッシュは `caddy hash-password` で生成し、平文パスワードは残さない。
    basic_auth {
        staff <bcrypt-hash>
    }

    # API への乱用抑制（IP あたり 60 回 / 分）
    @api path /api/*
    rate_limit @api {
        zone api_zone {
            key    {remote_host}
            events 60
            window 1m
        }
    }

    # /api/* は API サーバーへ
    handle /api/* {
        reverse_proxy 127.0.0.1:8001
    }

    # それ以外は Web画面へ
    handle {
        reverse_proxy 127.0.0.1:3001
    }
}
```

起動:
```bash
sudo caddy run --config /etc/caddy/Caddyfile
# または systemd 経由（caddy パッケージ標準の caddy.service）
```

> レート制限プラグインを入れない場合は `rate_limit` ブロックを削除し、レート制限は
> nginx（2B）か WAF/前段で行う。

---

## 2B. nginx（レート制限がビルトイン）

証明書は certbot（Let's Encrypt）で取得済みとする。

```nginx
# /etc/nginx/conf.d/oya-inai-db.conf

# レート制限ゾーン（http ブロックに置く）
limit_req_zone $binary_remote_addr zone=api_zone:10m rate=60r/m;

server {
    listen 443 ssl http2;
    server_name example.org;

    ssl_certificate     /etc/letsencrypt/live/example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.org/privkey.pem;

    # アプリ側に認証がないため、前段で必ずアクセス制御をかける
    auth_basic           "oya-inai-db";
    auth_basic_user_file /etc/nginx/.htpasswd;

    # API
    location /api/ {
        limit_req zone=api_zone burst=20 nodelay;
        proxy_pass http://127.0.0.1:8001;
        include proxy_params;
    }

    # Web画面
    location / {
        proxy_pass http://127.0.0.1:3001;
        include proxy_params;
    }
}

# HTTP → HTTPS リダイレクト
server {
    listen 80;
    server_name example.org;
    return 301 https://$host$request_uri;
}
```

`/etc/nginx/proxy_params`（無ければ作成）:
```nginx
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

---

## 3. アプリの起動（systemd 例）

`127.0.0.1` バインドで常駐させる。`.env` はプロジェクトルートから読まれる。

```ini
# /etc/systemd/system/oya-inai-api.service
[Unit]
Description=oya-inai-db API (FastAPI)
After=network.target docker.service

[Service]
WorkingDirectory=/opt/oya-inai-db/api
ExecStart=/usr/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=on-failure
User=nest

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/oya-inai-web.service
[Unit]
Description=oya-inai-db Web画面 (Next.js)
After=network.target

[Service]
WorkingDirectory=/opt/oya-inai-db/frontend
ExecStart=/usr/bin/pnpm exec next start --hostname 127.0.0.1 --port 3001
Restart=on-failure
User=nest

[Install]
WantedBy=multi-user.target
```

Web画面は事前にビルドしておく（`NEXT_PUBLIC_API_URL` はビルド時に埋め込まれる）:

```bash
cd /opt/oya-inai-db/frontend && pnpm install && pnpm build
```

```bash
sudo systemctl enable --now oya-inai-api oya-inai-web
```

Neo4j は `docker compose up -d neo4j`（`restart: unless-stopped` 指定済み）で常駐する。

---

## 4. 運用前の最終チェック

- [ ] Neo4j のパスワードを既定の `password` から変更した
- [ ] Neo4j の 7687 / 7474 が外部に公開されていない
- [ ] API（8001）と Web画面（3001）が `127.0.0.1` バインドになっている
- [ ] プロキシで TLS 終端・HTTP→HTTPS リダイレクトが効く
- [ ] **プロキシでアクセス制御（Basic 認証・IP 制限・VPN 等）をかけた**（アプリ内に認証はない）
- [ ] `/api/*` にレート制限が効く
- [ ] `NEXT_PUBLIC_API_URL` を公開ドメインに設定してから `pnpm build` した
- [ ] Claude での登録・照会を**どのパソコンで行うか**を決めた（MCP は Neo4j と同じ機上でのみ動く）
- [ ] `./scripts/doctor.sh` が All PASS（Neo4j 疎通・`.env`・API 8001・フロント 3001）
- [ ] Neo4j のバックアップ（`scripts/backup.sh`）を cron 等に登録した
