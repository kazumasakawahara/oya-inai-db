"""
Web Speech API を使った音声入力コンポーネント
Streamlit の st.components.v1.html で使用
"""

import streamlit.components.v1 as components


def render_voice_input(target_key: str = "voice_transcript", height: int = 200) -> None:
    """
    Web Speech API を使った音声入力コンポーネントをレンダリング

    Args:
        target_key: セッションステートのキー名
        height: コンポーネントの高さ（px）
    """

    html_code = f"""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: transparent;
                padding: 8px;
            }}

            .voice-container {{
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}

            .controls {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            .mic-button {{
                width: 56px;
                height: 56px;
                border-radius: 50%;
                border: none;
                background: #4CAF50;
                color: white;
                font-size: 24px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
                flex-shrink: 0;
            }}

            .mic-button:hover {{
                background: #45a049;
                transform: scale(1.05);
            }}

            .mic-button.recording {{
                background: #f44336;
                animation: pulse 1s infinite;
            }}

            .mic-button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}

            @keyframes pulse {{
                0%, 100% {{ transform: scale(1); }}
                50% {{ transform: scale(1.1); }}
            }}

            .status {{
                font-size: 14px;
                color: #666;
                flex: 1;
            }}

            .status.recording {{
                color: #f44336;
                font-weight: bold;
            }}

            .transcript-box {{
                background: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                min-height: 60px;
                max-height: 100px;
                overflow-y: auto;
                font-size: 14px;
                line-height: 1.5;
            }}

            .transcript-box .interim {{
                color: #888;
            }}

            .transcript-box:empty::before {{
                content: "🎤 マイクボタンを押して話してください";
                color: #999;
            }}

            .action-row {{
                display: flex;
                gap: 8px;
            }}

            .copy-btn, .clear-btn {{
                flex: 1;
                padding: 10px;
                border-radius: 8px;
                border: none;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.2s;
            }}

            .copy-btn {{
                background: #2196F3;
                color: white;
            }}

            .copy-btn:hover {{
                background: #1976D2;
            }}

            .copy-btn:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}

            .clear-btn {{
                background: #eee;
                color: #666;
            }}

            .clear-btn:hover {{
                background: #ddd;
            }}

            .error-message {{
                background: #ffebee;
                color: #c62828;
                padding: 10px;
                border-radius: 8px;
                font-size: 13px;
            }}

            .not-supported {{
                background: #fff3e0;
                color: #e65100;
                padding: 12px;
                border-radius: 8px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="voice-container" id="voiceContainer">
            <!-- JavaScript で動的に生成 -->
        </div>

        <script>
            const container = document.getElementById('voiceContainer');

            // Web Speech API サポートチェック
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (!SpeechRecognition) {{
                container.innerHTML = `
                    <div class="not-supported">
                        ⚠️ このブラウザは音声入力に対応していません<br>
                        <small>Chrome, Safari, Edge などをお使いください</small>
                    </div>
                `;
            }} else {{
                // 音声認識インスタンス
                const recognition = new SpeechRecognition();
                recognition.lang = 'ja-JP';
                recognition.continuous = true;
                recognition.interimResults = true;

                let finalTranscript = '';
                let isRecording = false;

                // UI 生成
                container.innerHTML = `
                    <div class="controls">
                        <button class="mic-button" id="micBtn" title="音声入力">🎤</button>
                        <span class="status" id="status">タップして音声入力</span>
                    </div>
                    <div class="transcript-box" id="transcript"></div>
                    <div class="action-row">
                        <button class="copy-btn" id="copyBtn" disabled>📋 コピーしてテキストエリアに貼り付け</button>
                        <button class="clear-btn" id="clearBtn">🗑️</button>
                    </div>
                `;

                const micBtn = document.getElementById('micBtn');
                const status = document.getElementById('status');
                const transcriptEl = document.getElementById('transcript');
                const copyBtn = document.getElementById('copyBtn');
                const clearBtn = document.getElementById('clearBtn');

                // マイクボタンクリック
                micBtn.addEventListener('click', () => {{
                    if (isRecording) {{
                        recognition.stop();
                    }} else {{
                        try {{
                            recognition.start();
                        }} catch (e) {{
                            // 既に開始している場合
                            recognition.stop();
                            setTimeout(() => recognition.start(), 100);
                        }}
                    }}
                }});

                // 認識開始
                recognition.onstart = () => {{
                    isRecording = true;
                    micBtn.classList.add('recording');
                    micBtn.textContent = '⏹️';
                    status.classList.add('recording');
                    status.textContent = '🔴 録音中... もう一度タップで停止';
                }};

                // 認識終了
                recognition.onend = () => {{
                    isRecording = false;
                    micBtn.classList.remove('recording');
                    micBtn.textContent = '🎤';
                    status.classList.remove('recording');
                    status.textContent = finalTranscript ? '✅ 認識完了' : 'タップして音声入力';
                }};

                // 認識結果
                recognition.onresult = (event) => {{
                    let interimTranscript = '';

                    for (let i = event.resultIndex; i < event.results.length; i++) {{
                        const transcript = event.results[i][0].transcript;
                        if (event.results[i].isFinal) {{
                            finalTranscript += transcript;
                        }} else {{
                            interimTranscript += transcript;
                        }}
                    }}

                    transcriptEl.innerHTML = finalTranscript +
                        (interimTranscript ? `<span class="interim">${{interimTranscript}}</span>` : '');

                    copyBtn.disabled = !finalTranscript;

                    // ローカルストレージに保存（Streamlit連携用）
                    if (finalTranscript) {{
                        localStorage.setItem('{target_key}', finalTranscript);
                    }}
                }};

                // エラー処理
                recognition.onerror = (event) => {{
                    console.error('Speech recognition error:', event.error);
                    isRecording = false;
                    micBtn.classList.remove('recording');
                    micBtn.textContent = '🎤';
                    status.classList.remove('recording');

                    let errorMsg = '音声認識エラー';
                    switch (event.error) {{
                        case 'not-allowed':
                            errorMsg = 'マイクへのアクセスが拒否されました。ブラウザの設定を確認してください。';
                            break;
                        case 'no-speech':
                            errorMsg = '音声が検出されませんでした。もう一度お試しください。';
                            break;
                        case 'audio-capture':
                            errorMsg = 'マイクが見つかりません。マイクを接続してください。';
                            break;
                        case 'network':
                            errorMsg = 'ネットワークエラー。インターネット接続を確認してください。';
                            break;
                    }}

                    status.textContent = '❌ ' + errorMsg;
                }};

                // コピーボタン
                copyBtn.addEventListener('click', async () => {{
                    if (finalTranscript) {{
                        try {{
                            await navigator.clipboard.writeText(finalTranscript);
                            copyBtn.textContent = '✅ コピーしました！';
                            setTimeout(() => {{
                                copyBtn.textContent = '📋 コピーしてテキストエリアに貼り付け';
                            }}, 2000);
                        }} catch (e) {{
                            // フォールバック: 選択してコピー
                            const range = document.createRange();
                            range.selectNode(transcriptEl);
                            window.getSelection().removeAllRanges();
                            window.getSelection().addRange(range);
                            document.execCommand('copy');
                            window.getSelection().removeAllRanges();
                            copyBtn.textContent = '✅ コピーしました！';
                            setTimeout(() => {{
                                copyBtn.textContent = '📋 コピーしてテキストエリアに貼り付け';
                            }}, 2000);
                        }}
                    }}
                }});

                // クリアボタン
                clearBtn.addEventListener('click', () => {{
                    finalTranscript = '';
                    transcriptEl.innerHTML = '';
                    copyBtn.disabled = true;
                    status.textContent = 'タップして音声入力';
                    localStorage.removeItem('{target_key}');
                }});

                // 前回の録音があれば復元
                const saved = localStorage.getItem('{target_key}');
                if (saved) {{
                    finalTranscript = saved;
                    transcriptEl.textContent = saved;
                    copyBtn.disabled = false;
                    status.textContent = '✅ 前回の録音があります';
                }}
            }}
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height)


def get_voice_input_instructions() -> str:
    """音声入力の使い方説明を返す"""
    return """
    **🎤 音声入力の使い方**
    1. マイクボタンをタップ
    2. 話し終わったらもう一度タップ
    3. 「コピー」ボタンをタップ
    4. 上のテキストエリアに貼り付け (長押し → 貼り付け)
    """
