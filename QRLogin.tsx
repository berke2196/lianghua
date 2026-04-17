"""
Electron React - 扫码登录页面组件
QR Code Login Page Component
"""

import React, { useState, useEffect, useCallback } from 'react';

// 这个文件的TypeScript/React版本应该是:
// src/frontend/renderer/pages/QRLogin.tsx

const QRLogin: React.FC = () => {
  const [qrCode, setQrCode] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [userInfo, setUserInfo] = useState<any>(null);

  useEffect(() => {
    // 启动应用时自动生成QR码
    const generateQRCode = async () => {
      try {
        setLoading(true);
        // 调用后端生成QR码
        const response = await fetch('/api/auth/generate-qr', {
          method: 'POST'
        });
        
        if (response.ok) {
          const data = await response.json();
          setQrCode(data.qr_code_base64);
          setError(null);
          
          // 开始轮询检查认证状态
          pollAuthStatus(data.session_id);
        } else {
          setError('生成QR码失败');
        }
      } catch (err) {
        setError('连接后端失败');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    generateQRCode();
  }, []);

  const pollAuthStatus = useCallback(async (sessionId: string) => {
    // 每2秒检查一次认证状态
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/auth/status/${sessionId}`);
        
        if (response.ok) {
          const data = await response.json();
          
          if (data.authenticated) {
            setAuthenticated(true);
            setUserInfo(data.user_info);
            clearInterval(pollInterval);
            
            // 2秒后跳转到主界面
            setTimeout(() => {
              window.location.href = '/dashboard';
            }, 2000);
          }
        }
      } catch (err) {
        console.error('轮询失败:', err);
      }
    }, 2000);

    // 10分钟后停止轮询
    setTimeout(() => clearInterval(pollInterval), 600000);
  }, []);

  if (authenticated) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="text-center">
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-4xl font-bold text-gray-800 mb-2">认证成功!</h1>
          <p className="text-xl text-gray-600 mb-4">
            欢迎, {userInfo?.username || userInfo?.user_id}
          </p>
          <p className="text-lg text-indigo-600 animate-pulse">
            正在加载交易界面...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md w-full">
        {/* 标题 */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            🚀 开始交易
          </h1>
          <p className="text-gray-600">
            使用 Hyperliquid App 扫码登录
          </p>
        </div>

        {/* QR码显示区域 */}
        <div className="flex justify-center mb-8">
          {loading ? (
            <div className="w-64 h-64 bg-gray-100 rounded-lg flex items-center justify-center">
              <div className="animate-spin">
                <svg
                  className="w-12 h-12 text-indigo-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
              </div>
            </div>
          ) : error ? (
            <div className="w-64 h-64 bg-red-50 rounded-lg flex items-center justify-center border-2 border-red-200">
              <div className="text-center">
                <div className="text-4xl mb-2">❌</div>
                <p className="text-red-600 font-semibold">{error}</p>
              </div>
            </div>
          ) : qrCode ? (
            <div className="bg-white p-4 rounded-lg border-2 border-gray-200">
              <img
                src={`data:image/png;base64,${qrCode}`}
                alt="QR Code"
                className="w-64 h-64"
              />
            </div>
          ) : null}
        </div>

        {/* 说明文字 */}
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-8 rounded">
          <p className="text-blue-800 font-semibold mb-2">📱 操作步骤:</p>
          <ol className="text-blue-700 text-sm space-y-1">
            <li>1. 打开 Hyperliquid App</li>
            <li>2. 点击"扫码登录"或"QR码"</li>
            <li>3. 对准上方二维码扫描</li>
            <li>4. 在 App 中点击"授权"</li>
            <li>5. 自动跳转到交易界面</li>
          </ol>
        </div>

        {/* 帮助信息 */}
        <div className="bg-gray-50 p-4 rounded-lg mb-6">
          <p className="text-gray-600 text-sm text-center">
            💡 如果二维码无法显示,
            <button
              onClick={() => window.location.reload()}
              className="text-indigo-600 hover:text-indigo-700 underline ml-1"
            >
              刷新页面
            </button>
          </p>
        </div>

        {/* 底部提示 */}
        <div className="text-center text-xs text-gray-500">
          <p>此登录方式100%安全</p>
          <p>您的API密钥不会被存储</p>
        </div>
      </div>

      {/* 页脚 */}
      <div className="mt-8 text-gray-600 text-sm">
        <p>
          需要帮助? 查看{' '}
          <a href="#" className="text-indigo-600 hover:underline">
            文档
          </a>
        </p>
      </div>
    </div>
  );
};

export default QRLogin;

/*
使用说明:

1. 在 App.tsx 中导入:
   import QRLogin from './pages/QRLogin';

2. 在路由中添加:
   <Route path="/login" element={<QRLogin />} />

3. 在未认证状态下重定向到这个页面:
   if (!isAuthenticated) {
     return <Navigate to="/login" replace />;
   }

4. 后端需要提供以下API端点:
   POST /api/auth/generate-qr
   - 返回: { qr_code_base64, session_id }
   
   GET /api/auth/status/:sessionId
   - 返回: { authenticated, user_info, ... }

5. 配置 OAuth 回调地址:
   在 Hyperliquid 的应用设置中设置:
   http://localhost:3000/auth/callback
*/
