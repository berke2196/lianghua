"""
⭐ AsterDex 自动交易系统 - 桌面应用
独立的PyQt6应用，支持做空做多、自动交易
"""

import sys
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QSpinBox, QDoubleSpinBox, QMessageBox, QDialog, QProgressBar,
    QStatusBar, QTextEdit, QFormLayout, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtCore import QSize
import aiohttp

from asterdex_api import AsterDexAPI
from trading_engine import (
    AutoTradingEngine, MomentumStrategy, MeanReversionStrategy,
    TrendFollowingStrategy, OrderSide, PositionSide
)


class APIWorker(QThread):
    """后台API工作线程"""
    update_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, api: AsterDexAPI, task_name: str, **kwargs):
        super().__init__()
        self.api = api
        self.task_name = task_name
        self.kwargs = kwargs
        self.running = True

    def run(self):
        """运行异步任务"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._execute_task())
            self.update_signal.emit({"task": self.task_name, "data": result})
        except Exception as e:
            self.error_signal.emit(f"{self.task_name} 失败: {str(e)}")
        finally:
            self.running = False

    async def _execute_task(self):
        """执行具体任务"""
        if self.task_name == "balance":
            return await self.api.get_balance()
        elif self.task_name == "ticker":
            return await self.api.get_ticker(self.kwargs.get("symbol"))
        elif self.task_name == "positions":
            return await self.api.get_positions()
        elif self.task_name == "trades":
            return await self.api.get_trades(self.kwargs.get("symbol"))
        elif self.task_name == "place_order":
            return await self.api.place_order(
                symbol=self.kwargs.get("symbol"),
                side=self.kwargs.get("side"),
                size=self.kwargs.get("size"),
                price=self.kwargs.get("price"),
                leverage=self.kwargs.get("leverage", 1)
            )
        elif self.task_name == "close_position":
            return await self.api.close_position(self.kwargs.get("symbol"))


class LoginDialog(QDialog):
    """登录对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.api_key = None
        self.api_secret = None
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("🔐 AsterDex 登录")
        self.setGeometry(100, 100, 400, 250)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; }
            QLabel { color: #ffffff; font-size: 12px; }
            QLineEdit { background-color: #2a2a2a; color: #ffffff; border: 1px solid #444; padding: 5px; }
            QPushButton { background-color: #f5a623; color: #000; font-weight: bold; padding: 8px; border: none; }
            QPushButton:hover { background-color: #ffb84d; }
        """)

        layout = QFormLayout()
        layout.setSpacing(15)

        title = QLabel("🔐 AsterDex 登录")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        layout.addRow(title)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("输入 API Key")
        layout.addRow("API Key:", self.key_input)

        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("输入 API Secret")
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("API Secret:", self.secret_input)

        button_layout = QHBoxLayout()
        login_btn = QPushButton("✅ 登录")
        login_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(login_btn)
        button_layout.addWidget(cancel_btn)
        layout.addRow(button_layout)

        self.setLayout(layout)

    def get_credentials(self):
        """获取登录凭证"""
        if self.exec() == QDialog.DialogCode.Accepted:
            return self.key_input.text(), self.secret_input.text()
        return None, None


class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.api: Optional[AsterDexAPI] = None
        self.engine: Optional[AutoTradingEngine] = None
        self.init_ui()
        self.show_login()

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("⭐ AsterDex 自动交易系统")
        self.setGeometry(0, 0, 1400, 900)
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
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("⭐ AsterDex 自动交易系统")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_layout.addWidget(title)

        user_info = QLabel("未登录")
        self.user_info = user_info
        title_layout.addStretch()
        title_layout.addWidget(user_info)

        logout_btn = QPushButton("🚪 登出")
        logout_btn.clicked.connect(self.logout)
        title_layout.addWidget(logout_btn)
        main_layout.addLayout(title_layout)

        # 标签页
        tabs = QTabWidget()

        # 交易页面
        self.trading_tab = self.create_trading_tab()
        tabs.addTab(self.trading_tab, "💰 交易")

        # 持仓页面
        self.positions_tab = self.create_positions_tab()
        tabs.addTab(self.positions_tab, "📊 持仓")

        # 交易历史页面
        self.history_tab = self.create_history_tab()
        tabs.addTab(self.history_tab, "📝 历史")

        # 自动交易页面
        self.auto_tab = self.create_auto_trading_tab()
        tabs.addTab(self.auto_tab, "🤖 自动交易")

        main_layout.addWidget(tabs)

        # 状态栏
        self.statusBar().showMessage("✅ 就绪")

        central_widget.setLayout(main_layout)

        # 定时刷新
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(5000)

    def create_trading_tab(self):
        """创建交易标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 实时数据
        info_layout = QHBoxLayout()
        self.balance_label = QLabel("余额: ¥0.00")
        self.balance_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.balance_label.setStyleSheet("color: #f5a623;")
        info_layout.addWidget(self.balance_label)

        self.price_label = QLabel("BTCUSDT: ¥0.00")
        self.price_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addWidget(self.price_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # 下单表单
        form_layout = QHBoxLayout()

        # 交易对选择
        form_layout.addWidget(QLabel("交易对:"))
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        form_layout.addWidget(self.symbol_combo)

        # 买卖选择
        form_layout.addWidget(QLabel("方向:"))
        self.side_combo = QComboBox()
        self.side_combo.addItems(["🟢 买入", "🔴 卖出"])
        form_layout.addWidget(self.side_combo)

        # 数量
        form_layout.addWidget(QLabel("数量:"))
        self.size_input = QDoubleSpinBox()
        self.size_input.setValue(1.0)
        self.size_input.setMinimum(0.001)
        form_layout.addWidget(self.size_input)

        # 价格
        form_layout.addWidget(QLabel("价格:"))
        self.price_input = QDoubleSpinBox()
        self.price_input.setValue(0)
        form_layout.addWidget(self.price_input)

        # 杠杆
        form_layout.addWidget(QLabel("杠杆:"))
        self.leverage_spin = QSpinBox()
        self.leverage_spin.setValue(1)
        self.leverage_spin.setMaximum(10)
        form_layout.addWidget(self.leverage_spin)

        # 下单按钮
        order_btn = QPushButton("📤 下单")
        order_btn.clicked.connect(self.place_order)
        form_layout.addWidget(order_btn)

        layout.addLayout(form_layout)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_positions_tab(self):
        """创建持仓标签页"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(8)
        self.positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%", "操作"]
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

        # 交易对
        strategy_layout.addWidget(QLabel("交易对:"))
        self.auto_symbol_combo = QComboBox()
        self.auto_symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        strategy_layout.addWidget(self.auto_symbol_combo)

        # 启动/停止按钮
        self.auto_start_btn = QPushButton("🚀 启动")
        self.auto_start_btn.clicked.connect(self.start_auto_trading)
        strategy_layout.addWidget(self.auto_start_btn)

        self.auto_stop_btn = QPushButton("⏹️ 停止")
        self.auto_stop_btn.clicked.connect(self.stop_auto_trading)
        self.auto_stop_btn.setEnabled(False)
        strategy_layout.addWidget(self.auto_stop_btn)

        layout.addLayout(strategy_layout)

        # 统计信息
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel(
            "总交易: 0 | 胜率: 0% | 总盈亏: ¥0.00 | 活跃持仓: 0"
        )
        self.stats_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.stats_label.setStyleSheet("color: #f5a623;")
        stats_layout.addWidget(self.stats_label)
        layout.addLayout(stats_layout)

        # 活跃持仓
        self.auto_positions_table = QTableWidget()
        self.auto_positions_table.setColumnCount(7)
        self.auto_positions_table.setHorizontalHeaderLabels(
            ["交易对", "方向", "数量", "开仓价", "当前价", "未实现盈亏", "盈亏%"]
        )
        layout.addWidget(self.auto_positions_table)

        # 日志
        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setMaximumHeight(150)
        layout.addWidget(QLabel("📋 交易日志:"))
        layout.addWidget(self.auto_log)

        widget.setLayout(layout)
        return widget

    def show_login(self):
        """显示登录对话框"""
        dialog = LoginDialog(self)
        api_key, api_secret = dialog.get_credentials()

        if api_key and api_secret:
            self.api = AsterDexAPI(api_key, api_secret, testnet=False)
            self.engine = AutoTradingEngine(self.api, "trader_001")
            self.user_info.setText(f"✅ 已登录: {api_key[:10]}...")
            self.statusBar().showMessage("✅ 已登录 AsterDex")
            self.refresh_data()
        else:
            self.statusBar().showMessage("❌ 登录取消")
            sys.exit()

    def logout(self):
        """登出"""
        if self.engine and self.engine.is_running:
            self.engine.stop_auto_trading()
        self.api = None
        self.engine = None
        self.show_login()

    def refresh_data(self):
        """刷新数据"""
        if not self.api:
            return

        # 更新余额
        worker = APIWorker(self.api, "balance")
        worker.update_signal.connect(self.on_api_response)
        worker.error_signal.connect(self.on_api_error)
        worker.start()

        # 更新价格
        symbol = self.symbol_combo.currentText() or "BTCUSDT"
        worker = APIWorker(self.api, "ticker", symbol=symbol)
        worker.update_signal.connect(self.on_api_response)
        worker.start()

        # 更新持仓
        worker = APIWorker(self.api, "positions")
        worker.update_signal.connect(self.on_api_response)
        worker.start()

    def on_api_response(self, data):
        """处理API响应"""
        task = data.get("task")
        result = data.get("data")

        if task == "balance" and result:
            balance = result.get("available_balance", 0)
            self.balance_label.setText(f"余额: ¥{balance:.2f}")

        elif task == "ticker" and result:
            price = result.get("price", 0)
            change = result.get("change_24h", 0)
            symbol = self.symbol_combo.currentText() or "BTCUSDT"
            self.price_label.setText(f"{symbol}: ¥{price:.2f} ({change:+.2f}%)")

        elif task == "positions" and result:
            self.positions_table.setRowCount(len(result))
            for row, pos in enumerate(result):
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

    def on_api_error(self, error):
        """处理API错误"""
        QMessageBox.warning(self, "错误", error)

    def place_order(self):
        """下单"""
        if not self.api:
            QMessageBox.warning(self, "错误", "请先登录")
            return

        symbol = self.symbol_combo.currentText()
        side = "BUY" if "买" in self.side_combo.currentText() else "SELL"
        size = self.size_input.value()
        price = self.price_input.value() if self.price_input.value() > 0 else None
        leverage = self.leverage_spin.value()

        worker = APIWorker(
            self.api, "place_order",
            symbol=symbol, side=side, size=size, price=price, leverage=leverage
        )
        worker.update_signal.connect(lambda data: self.on_order_placed(data))
        worker.error_signal.connect(self.on_api_error)
        worker.start()

    def on_order_placed(self, data):
        """订单已下单"""
        result = data.get("data")
        if result:
            QMessageBox.information(self, "✅ 成功", f"订单已下单: {result.get('order_id')}")
            self.refresh_data()

    def start_auto_trading(self):
        """启动自动交易"""
        if not self.engine:
            return

        strategy_index = self.strategy_combo.currentIndex()
        strategy_names = ["momentum", "mean_reversion", "trend_following"]
        symbol = self.auto_symbol_combo.currentText()

        asyncio.run(self.engine.start_auto_trading(symbol, strategy_names[strategy_index]))
        self.auto_start_btn.setEnabled(False)
        self.auto_stop_btn.setEnabled(True)
        self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 已启动 {strategy_names[strategy_index]} 策略")

    def stop_auto_trading(self):
        """停止自动交易"""
        if self.engine:
            self.engine.stop_auto_trading()
            self.auto_start_btn.setEnabled(True)
            self.auto_stop_btn.setEnabled(False)
            self.auto_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ 已停止自动交易")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    window = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
