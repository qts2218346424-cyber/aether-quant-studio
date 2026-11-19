"""Aether Quant Studio · 启动过渡与加载屏模板"""

SPLASH_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Aether Quant Studio · 苍穹量枢</title>
  <style>
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
    }
    body {
      background: radial-gradient(circle at 50% 30%, #161b26 0%, #0b0e14 100%);
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .logo-container {
      position: relative;
      width: 110px;
      height: 110px;
      margin-bottom: 28px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .spinner-ring {
      position: absolute;
      width: 100%;
      height: 100%;
      border-radius: 50%;
      border: 3px solid rgba(240, 185, 11, 0.12);
      border-top-color: #f0b90b;
      animation: spin 1.2s cubic-bezier(0.55, 0.15, 0.45, 0.85) infinite;
    }
    .spinner-glow {
      position: absolute;
      width: 90px;
      height: 90px;
      border-radius: 50%;
      background: rgba(240, 185, 11, 0.08);
      filter: blur(12px);
    }
    .logo-diamond {
      width: 44px;
      height: 44px;
      background: #f0b90b;
      transform: rotate(45deg);
      border-radius: 6px;
      box-shadow: 0 0 24px rgba(240, 185, 11, 0.55);
      position: relative;
    }
    .logo-diamond::after {
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      background: #0b0e14;
      top: 13px;
      left: 13px;
      border-radius: 3px;
    }
    h1 {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 1.5px;
      color: #ffffff;
      margin-bottom: 8px;
      text-align: center;
    }
    .highlight {
      color: #f0b90b;
    }
    .subtitle {
      font-size: 13px;
      color: #94a3b8;
      letter-spacing: 0.8px;
      margin-bottom: 36px;
      text-align: center;
    }
    .status-box {
      display: flex;
      align-items: center;
      gap: 10px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 10px 22px;
      border-radius: 24px;
      backdrop-filter: blur(10px);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #f0b90b;
      border-radius: 50%;
      box-shadow: 0 0 8px #f0b90b;
      animation: pulse 1.5s infinite;
    }
    .status-text {
      font-size: 12px;
      color: #cbd5e1;
      font-weight: 500;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    @keyframes pulse {
      0%, 100% { opacity: 0.4; transform: scale(0.9); }
      50% { opacity: 1; transform: scale(1.15); }
    }
  </style>
</head>
<body>
  <div class="logo-container">
    <div class="spinner-glow"></div>
    <div class="spinner-ring"></div>
    <div class="logo-diamond"></div>
  </div>
  <h1>AETHER <span class="highlight">QUANT STUDIO</span></h1>
  <div class="subtitle">苍穹量枢 · 个人量化玩具与币安合约多策略智能终端</div>
  <div class="status-box">
    <div class="pulse-dot"></div>
    <div class="status-text" id="status-desc">正在拉起量化核心引擎...</div>
  </div>

  <script>
    const statusDesc = document.getElementById("status-desc");
    const phrases = [
      "正在拉起量化核心引擎...",
      "连接本地数据库与安全账本...",
      "准备多因子模型与异步状态机...",
      "服务就绪，即将进入交易终端..."
    ];
    let phraseIndex = 0;
    setInterval(() => {
      if (phraseIndex < phrases.length - 1) {
        phraseIndex++;
        statusDesc.innerText = phrases[phraseIndex];
      }
    }, 800);
  </script>
</body>
</html>
"""
