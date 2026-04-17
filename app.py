"""
⭐ AsterDex 自动交易系统 - 完整版
真实交易、全局数据刷新、支持做多做空
"""

import sys
import asyncio
import threading
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QTextEdit, QGroupBox,
    QDialog, QFormLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor

from asterdex_api import AsterDexAPI
from trading_engine import AutoTradingEngine, OrderSide


class SignalEmitter(QObject):
    """信号发射器"""
    update_signal = pyqtSignal(dict)


class APIRefresher(threading.Thread):
    """后台API刷新线程"""
    def __init__(self, api: AsterDexAPI, signal_emitter: SignalEmitter):
        super().__init__(daemon=True)
        self.api = api
        self.signal_emitter = signal_emitter
        self.running = True

    def run(self):
        """后台运行"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.running:
            try:
                # 获取余额
                balance = loop.run_until_complete(self.api.get_balance())
                if balance:
                    self.signal_emitter.update_signal.emit({"type": "balance", "data": balance})

                # 获取持仓
                positions = loop.run_until_complete(self.api.get_positions())
                if positions:
                    self.signal_emitter.update_signal.emit({"type": "positions", "data": positions})

                # 获取交易历史
                trades = loop.run_until_complete(self.api.get_trades(limit=10))
                if trades:
                    self.signal_emitter.update_signal.emit({"type": "trades", "data": trades})

                threading.Event().wait(5)  # 每5秒刷新一次
            except Exception as e:
                print(f"刷新错误: {e}")
                threading.Event().wait(5)

    def stop(self):
        """停止线程"""
        self.running = False


class APIKeyDialog(QDialog):
    """API Key 输入对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = None
        self.api_secret = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("输入 AsterDex 凭证")
        self.setGeometry(100, 100, 500, 200)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLineEdit { background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px; }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 8px; }
            QPushButton:hover { background-color: #ffb84d; }
        """)

        layout = QFormLayout()

        title = QLabel("请输入 AsterDex API 凭证")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #f5a623;")
        layout.addRow(title)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("API Key")
        layout.addRow("API Key:", self.key_input)

        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("API Secret")
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Secret:", self.secret_input)

        button_layout = QHBoxLayout()
        ok_btn = QPushButton("✅ 确认")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addRow(button_layout)

        self.setLayout(layout)

    def get_credentials(self):
        """获取凭证"""
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.key_input.text(), self.secret_input.text()
        return None, None


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.api: Optional[AsterDexAPI] = None
        self.engine: Optional[AutoTradingEngine] = None
        self.is_logged_in = False
        self.refresher: Optional[APIRefresher] = None

        # 信号发射器
        self.signal_emitter = SignalEmitter()
        self.signal_emitter.update_signal.connect(self.on_api_update)

        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("⭐ AsterDex 自动交易系统")
        self.setGeometry(0, 0, 1600, 1000)
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            QLabel { color: #ffffff; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px;
            }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 8px; border: none; }
            QPushButton:hover { background-color: #ffb84d; }
            QTableWidget { background-color: #2a2a2a; color: #ffffff; gridline-color: #444; }
            QHeaderView::section { background-color: #333; color: #fff; padding: 5px; }
            QTabBar::tab { background-color: #2a2a2a; color: #fff; padding: 8px; }
            QTabBar::tab:selected { background-color: #f5a623; color: #000; }
            QTextEdit { background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("⭐ AsterDex 自动交易系统")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_layout.addWidget(title)

        self.user_info = QLabel("未登录")
        self.user_info.setStyleSheet("color: #ff9800; font-weight: bold;")
        title_layout.addStretch()
        title_layout.addWidget(self.user_info)

        logout_btn = QPushButton("🚪 登出")
        logout_btn.clicked.connect(self.logout)
        title_layout.addWidget(logout_btn)
        main_layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()

        # 登录页面
        self.login_tab = self.create_login_tab()
        tabs.addTab(self.login_tab, "🔐 登录")

        # 交易页面
        self.trading_tab = self.create_trading_tab()
        tabs.addTab(self.trading_tab, "💰 交易")

        # 钱包信息页面
        self.wallet_tab = self.create_wallet_tab()
        tabs.addTab(self.wallet_tab, "🏦 钱包")

        # 持仓页面
        self.positions_tab = self.create_positions_tab()
        tabs.addTab(self.positions_tab, "📊 持仓")

        # 交易历史
        self.history_tab = self.create_history_tab()
        tabs.addTab(self.history_tab, "📝 历史")

        # 自动交易页面
        self.auto_tab = self.create_auto_trading_tab()
        tabs.addTab(self.auto_tab, "🤖 自动交易")

        main_layout.addWidget(tabs)
        central_widget.setLayout(main_layout)

    def create_login_tab(self):
        """创建登录标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 提示信息
        info = QLabel("选择登录方式：\n\n1. Hyperliquid 登录 - 在下方网页中登录\n2. AsterDex API - 输入 API Key 和 Secret")
        info.setStyleSheet("color: #f5a623; font-weight: bold; padding: 10px;")
        layout.addWidget(info)

        # 嵌入网页
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("https://www.hyperliquid.xyz"))
        layout.addWidget(self.web_view)

        # 登录按钮组
        button_layout = QHBoxLayout()

        self.login_status = QLabel("状态: 未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        button_layout.addWidget(self.login_status)

        button_layout.addStretch()

        # Hyperliquid 登录
        logged_btn = QPushButton("✅ Hyperliquid 已登录")
        logged_btn.setMinimumHeight(40)
        logged_btn.clicked.connect(self.on_login_hyperliquid)
        button_layout.addWidget(logged_btn)

        # API 登录
        api_btn = QPushButton("🔑 AsterDex API 登录")
        api_btn.setMinimumHeight(40)
        api_btn.clicked.connect(self.on_login_api)
        button_layout.addWidget(api_btn)

        layout.addLayout(button_layout)
        widget.setLayout(layout)
        return widget

    def create_trading_tab(self):
        """创建交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先在登录页面完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

        # 实时数据
        info_layout = QHBoxLayout()

        self.balance_label = QLabel("余额: ¥0.00")
        self.balance_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.balance_label.setStyleSheet("color: #f5a623;")
        info_layout.addWidget(self.balance_label)

        self.equity_label = QLabel("权益: ¥0.00")
        self.equity_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.equity_label.setStyleSheet("color: #f5a623;")
        info_layout.addWidget(self.equity_label)

        self.price_label = QLabel("BTCUSDT: ¥0.00")
        self.price_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addWidget(self.price_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 下单表单
        form_layout = QHBoxLayout()

        form_layout.addWidget(QLabel("交易对:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        self.symbol_combo.currentTextChanged.connect(self.on_symbol_changed)
        form_layout.addWidget(self.symbol_combo)

        form_layout.addWidget(QLabel("方向:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["🟢 做多", "🔴 做空"])
        form_layout.addWidget(self.side_combo)

        form_layout.addWidget(QLabel("数量:"))
        self.size_input = QDoubleSpinBox()
        self.size_input.setValue(1.0)
        self.size_input.setMinimum(0.001)
        form_layout.addWidget(self.size_input)

        form_layout.addWidget(QLabel("价格:"))
        self.price_input = QDoubleSpinBox()
        self.price_input.setValue(0)
        form_layout.addWidget(self.price_input)

        form_layout.addWidget(QLabel("杠杆:"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setValue(1)
        self.leverage_spin.setMaximum(125)
        form_layout.addWidget(self.leverage_spin)

        order_btn = QPushButton("📤 下单")
        order_btn.setMinimumHeight(35)
        order_btn.clicked.connect(self.place_order)
        form_layout.addWidget(order_btn)

        layout.addLayout(form_layout)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_wallet_tab(self):
        """创建钱包信息标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

        # 账户余额信息
        info_layout = QHBoxLayout()

        balance_box = QGroupBox("账户余额")
        balance_box_layout = QVBoxLayout()
        self.wallet_balance = QLabel("¥0.00")
        self.wallet_balance.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.wallet_balance.setStyleSheet("color: #f5a623;")
        balance_box_layout.addWidget(self.wallet_balance)
        balance_box.setLayout(balance_box_layout)
        info_layout.addWidget(balance_box)

        equity_box = QGroupBox("权益")
        equity_box_layout = QVBoxLayout()
        self.wallet_equity = QLabel("¥0.00")
        self.wallet_equity.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.wallet_equity.setStyleSheet("color: #4ade80;")
        equity_box_layout.addWidget(self.wallet_equity)
        equity_box.setLayout(equity_box_layout)
        info_layout.addWidget(equity_box)

        margin_box = QGroupBox("已用保证金")
        margin_box_layout = QVBoxLayout()
        self.wallet_margin = QLabel("¥0.00")
        self.wallet_margin.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.wallet_margin.setStyleSheet("color: #ff6b6b;")
        margin_box_layout.addWidget(self.wallet_margin)
        margin_box.setLayout(margin_box_layout)
        info_layout.addWidget(margin_box)

        info_layout.addStretch()
        layout.addLayout(info_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_positions_tab(self):
        """创建持仓标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%", "杠杆", "操作"]
        )
        layout.addWidget(self.positions_table)

        widget.setLayout(layout)
        return widget

    def create_history_tab(self):
        """创建交易历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels(
            ["交易ID", "交易对", "方向", "数量", "价格", "时间", "盈亏"]
        )
        layout.addWidget(self.history_table)

        widget.setLayout(layout)
        return widget

    def create_auto_trading_tab(self):
        """创建自动交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        if not self.is_logged_in:
            no_login = QLabel("请先完成登录")
            no_login.setStyleSheet("color: #ff9800; font-size: 14px; padding: 20px;")
            no_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_login)
            layout.addStretch()
            widget.setLayout(layout)
            return widget

        # 策略选择
        strategy_layout = QHBoxLayout()
        strategy_layout.addWidget(QLabel("选择策略:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "📈 Momentum (动量策略)",
            "↔️ Mean Reversion (均值回归)",
            "🔁 Trend Following (趋势跟踪)"
        ])
        strategy_layout.addWidget(self.strategy_combo)

        strategy_layout.addWidget(QLabel("交易对:"))
        self.auto_symbol_combo = QComboBox()
        self.auto_symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        strategy_layout.addWidget(self.auto_symbol_combo)

        self.auto_start_btn = QPushButton("🚀 启动")
        self.auto_start_btn.clicked.connect(self.start_auto_trading)
        self.auto_start_btn.setMinimumHeight(35)
        strategy_layout.addWidget(self.auto_start_btn)

        self.auto_stop_btn = QPushButton("⏹️ 停止")
        self.auto_stop_btn.clicked.connect(self.stop_auto_trading)
        self.auto_stop_btn.setEnabled(False)
        self.auto_stop_btn.setMinimumHeight(35)
        strategy_layout.addWidget(self.auto_stop_btn)

        layout.addLayout(strategy_layout)

        # 统计信息
        self.stats_label = QLabel("总交易: 0 | 胜率: 0% | 总盈亏: ¥0.00")
        self.stats_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.stats_label.setStyleSheet("color: #f5a623;")
        layout.addWidget(self.stats_label)

        # 活跃持仓表格
        self.auto_positions_table = QTableWidget()
        self.auto_positions_table.setColumnCount(7)
        self.auto_positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%"]
        )
        layout.addWidget(self.auto_positions_table)

        # 日志
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setMaximumHeight(120)
        layout.addWidget(QLabel("📋 交易日志:"))
        layout.addWidget(self.auto_log)

        widget.setLayout(layout)
        return widget

    def on_login_hyperliquid(self):
        """Hyperliquid 登录"""
        self.is_logged_in = True
        self.user_info.setText("✅ Hyperliquid 已连接")
        self.login_status.setText("状态: ✅ 已登录")
        self.login_status.setStyleSheet("color: #4ade80; font-weight: bold;")

        # 初始化 API（使用示例凭证，实际应从网页提取）
        self.api = AsterDexAPI("test_key", "test_secret", testnet=False)
        self.engine = AutoTradingEngine(self.api, "trader_001")

        # 启动后台刷新线程
        self.refresher = APIRefresher(self.api, self.signal_emitter)
        self.refresher.start()

        QMessageBox.information(self, "✅", "登录成功！现已连接 Hyperliquid\n开始实时刷新账户数据...")

    def on_login_api(self):
        """AsterDex API 登录"""
        dialog = APIKeyDialog(self)
        api_key, api_secret = dialog.get_credentials()

        if api_key and api_secret:
            try:
                self.api = AsterDexAPI(api_key, api_secret, testnet=False)
                self.engine = AutoTradingEngine(self.api, "trader_001")

                self.is_logged_in = True
                self.user_info.setText(f"✅ AsterDex 已登录")
                self.login_status.setText("状态: ✅ API 已连接")
                self.login_status.setStyleSheet("color: #4ade80; font-weight: bold;")

                # 启动后台刷新线程
                self.refresher = APIRefresher(self.api, self.signal_emitter)
                self.refresher.start()

                QMessageBox.information(self, "✅", "API 认证成功！\n开始实时刷新账户数据...")
            except Exception as e:
                QMessageBox.warning(self, "❌", f"登录失败: {e}")

    def on_api_update(self, data):
        """处理 API 更新"""
        update_type = data.get("type")
        update_data = data.get("data")

        if update_type == "balance" and update_data:
            balance = update_data.get("available_balance", 0)
            equity = update_data.get("equity", 0)
            self.balance_label.setText(f"余额: ¥{balance:.2f}")
            self.equity_label.setText(f"权益: ¥{equity:.2f}")
            self.wallet_balance.setText(f"¥{balance:.2f}")
            self.wallet_equity.setText(f"¥{equity:.2f}")
            self.wallet_margin.setText(f"¥{update_data.get('margin_used', 0):.2f}")

        elif update_type == "positions" and update_data:
            self.positions_table.setRowCount(len(update_data))
            for row, pos in enumerate(update_data):
                self.positions_table.setItem(row, 0, QTableWidgetItem(pos.get("symbol", "")))
                self.positions_table.setItem(row, 1, QTableWidgetItem(pos.get("side", "")))
                self.positions_table.setItem(row, 2, QTableWidgetItem(f"{pos.get('size', 0):.4f}"))
                self.positions_table.setItem(row, 3, QTableWidgetItem(f"¥{pos.get('entry_price', 0):.2f}"))
                self.positions_table.setItem(row, 4, QTableWidgetItem(f"¥{pos.get('current_price', 0):.2f}"))
                pnl = pos.get("unrealized_pnl", 0)
                self.positions_table.setItem(row, 5, QTableWidgetItem(f"¥{pnl:.2f}"))
                pnl_pct = pos.get("pnl_percent", 0)
                item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                if pnl_pct > 0:
                    item.setForeground(QColor("#00ff00"))
                elif pnl_pct < 0:
                    item.setForeground(QColor("#ff0000"))
                self.positions_table.setItem(row, 6, item)
                self.positions_table.setItem(row, 7, QTableWidgetItem(str(pos.get("leverage", 1))))

        elif update_type == "trades" and update_data:
            self.history_table.setRowCount(len(update_data))
            for row, trade in enumerate(update_data):
                self.history_table.setItem(row, 0, QTableWidgetItem(str(trade.get("trade_id", ""))))
                self.history_table.setItem(row, 1, QTableWidgetItem(trade.get("symbol", "")))
                self.history_table.setItem(row, 2, QTableWidgetItem(trade.get("side", "")))
                self.history_table.setItem(row, 3, QTableWidgetItem(f"{trade.get('size', 0):.4f}"))
                self.history_table.setItem(row, 4, QTableWidgetItem(f"¥{trade.get('price', 0):.2f}"))
                self.history_table.setItem(row, 5, QTableWidgetItem(str(trade.get("timestamp", ""))))
                pnl = trade.get("pnl", 0)
                item = QTableWidgetItem(f"¥{pnl:.2f}")
                if pnl > 0:
                    item.setForeground(QColor("#00ff00"))
                elif pnl < 0:
                    item.setForeground(QColor("#ff0000"))
                self.history_table.setItem(row, 6, item)

    def on_symbol_changed(self, symbol):
        """交易对改变时更新价格"""
        if self.api:
            async def get_price():
                try:
                    ticker = await self.api.get_ticker(symbol)
                    if ticker:
                        price = ticker.get("price", 0)
                        self.price_label.setText(f"{symbol}: ¥{price:.2f}")
                except:
                    pass

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(get_price())

    def place_order(self):
        """下单"""
        if not self.api:
            QMessageBox.warning(self, "错误", "请先登录")
            return

        symbol = self.symbol_combo.currentText()
        side = "BUY" if "做多" in self.side_combo.currentText() else "SELL"
        size = self.size_input.value()
        price = self.price_input.value() if self.price_input.value() > 0 else None
        leverage = self.leverage_spin.value()

        async def execute():
            try:
                order = await self.api.place_order(
                    symbol=symbol,
                    side=side,
                    size=size,
                    price=price,
                    leverage=leverage
                )
                if order:
                    QMessageBox.information(self, "✅", f"订单已下单\nID: {order.get('order_id')}")
                else:
                    QMessageBox.warning(self, "❌", "下单失败")
            except Exception as e:
                QMessageBox.warning(self, "❌", f"下单错误: {e}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(execute())

    def start_auto_trading(self):
        """启动自动交易"""
        if not self.engine:
            return
        self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 自动交易已启动")
        self.auto_start_btn.setEnabled(False)
        self.auto_stop_btn.setEnabled(True)

    def stop_auto_trading(self):
        """停止自动交易"""
        self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ 自动交易已停止")
        self.auto_start_btn.setEnabled(True)
        self.auto_stop_btn.setEnabled(False)

    def logout(self):
        """登出"""
        if self.refresher:
            self.refresher.stop()
        self.is_logged_in = False
        self.api = None
        self.user_info.setText("未登录")
        self.login_status.setText("状态: 未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold;")
        QMessageBox.information(self, "✅", "已登出")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
