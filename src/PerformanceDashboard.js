import React from 'react';
import { Row, Col, Card, Statistic, Progress, Table, Tag, Empty, Tooltip } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, SmileOutlined, FrownOutlined, SisternodeOutlined } from '@ant-design/icons';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const PerformanceDashboard = ({ perf, tradeLogs, settings }) => {
  if (!perf || perf.total_trades === 0) {
    return (
      <Empty
        description="暂无交易数据"
        style={{ marginTop: 50 }}
      />
    );
  }

  const total_trades = perf.total_trades || 0;
  const wins = perf.wins || 0;
  const losses = perf.losses || 0;
  const win_rate = perf.win_rate || 0;
  const total_pnl = perf.total_pnl || 0;
  const total_pnl_pct = perf.total_pnl_pct || 0;
  const daily_pnl = perf.daily_pnl || 0;
  const daily_pnl_pct = perf.daily_pnl_pct || 0;

  // 处理K线数据用于图表
  const closedTrades = tradeLogs.filter(t => t.side === "CLOSE");

  let cumulativePnl = 0;
  const pnlData = closedTrades.map((trade, idx) => {
    cumulativePnl += trade.pnl || 0;
    return {
      time: trade.time || `#${idx}`,
      pnl: trade.pnl || 0,
      cumulative: parseFloat(cumulativePnl.toFixed(2)),
    };
  }).slice(-50); // 最多显示最近50笔

  // 每日盈亏统计
  const dailyStats = Object.entries(perf.daily_history || {}).map(([date, stats]) => ({
    date,
    pnl: stats.pnl || 0,
    trades: stats.trades || 0,
    wins: stats.wins || 0,
  })).slice(-30); // 最多显示30天

  // 交易类型分布
  const symbolStats = {};
  closedTrades.forEach(trade => {
    const sym = trade.symbol;
    if (!symbolStats[sym]) {
      symbolStats[sym] = { wins: 0, losses: 0, pnl: 0 };
    }
    symbolStats[sym].pnl += trade.pnl || 0;
    if (trade.pnl > 0) symbolStats[sym].wins += 1;
    else if (trade.pnl < 0) symbolStats[sym].losses += 1;
  });

  const symbolTableData = Object.entries(symbolStats).map(([symbol, stats]) => ({
    symbol,
    ...stats,
    winRate: stats.wins + stats.losses > 0 ? ((stats.wins / (stats.wins + stats.losses)) * 100).toFixed(1) : 0,
  }));

  return (
    <div style={{ padding: '20px' }}>
      {/* 核心指标 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总成交笔数"
              value={total_trades}
              prefix={<SisternodeOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="胜率"
              value={win_rate}
              suffix="%"
              precision={1}
              valueStyle={{ color: win_rate >= 50 ? '#52c41a' : '#ff4d4f' }}
              prefix={win_rate >= 50 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="总收益"
              value={total_pnl}
              prefix="$"
              precision={2}
              valueStyle={{ color: total_pnl >= 0 ? '#52c41a' : '#ff4d4f' }}
            />
            <div style={{ fontSize: 12, marginTop: 8, color: '#999' }}>
              占比 {total_pnl_pct}%
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="今日收益"
              value={daily_pnl}
              prefix="$"
              precision={2}
              valueStyle={{ color: daily_pnl >= 0 ? '#52c41a' : '#ff4d4f' }}
            />
            <div style={{ fontSize: 12, marginTop: 8, color: '#999' }}>
              占比 {daily_pnl_pct}%
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {/* 盈亏曲线 */}
        <Col xs={24} md={12}>
          <Card title="累计收益曲线（最近50笔）" extra={<span style={{fontSize:12, color:'#999'}}>{closedTrades.length} 笔平仓</span>}>
            {pnlData.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={pnlData}>
                  <defs>
                    <linearGradient id="colorCum" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="#8884d8" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <ChartTooltip />
                  <Area type="monotone" dataKey="cumulative" stroke="#8884d8" fill="url(#colorCum)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
        </Col>

        {/* 每日统计 */}
        <Col xs={24} md={12}>
          <Card title="每日收益（最近30天）">
            {dailyStats.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={dailyStats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <ChartTooltip />
                  <Bar dataKey="pnl" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            ) : <Empty />}
          </Card>
        </Col>
      </Row>

      {/* 币种详情 */}
      <Card title="币种分析" style={{ marginTop: 16 }}>
        <Table
          columns={[
            {
              title: '币种',
              dataIndex: 'symbol',
              key: 'symbol',
              render: (text) => <strong>{text}</strong>,
            },
            {
              title: '平仓数',
              dataIndex: 'trades',
              key: 'trades',
              align: 'center',
            },
            {
              title: '胜数',
              dataIndex: 'wins',
              key: 'wins',
              align: 'center',
              render: (text) => <Tag color="green">{text}</Tag>,
            },
            {
              title: '负数',
              dataIndex: 'losses',
              key: 'losses',
              align: 'center',
              render: (text) => <Tag color="red">{text}</Tag>,
            },
            {
              title: '胜率',
              dataIndex: 'winRate',
              key: 'winRate',
              align: 'center',
              render: (text) => (
                <span style={{ color: parseFloat(text) >= 50 ? '#52c41a' : '#ff4d4f' }}>
                  {text}%
                </span>
              ),
            },
            {
              title: '总收益',
              dataIndex: 'pnl',
              key: 'pnl',
              align: 'right',
              render: (text) => (
                <span style={{
                  color: text >= 0 ? '#52c41a' : '#ff4d4f',
                  fontWeight: 'bold'
                }}>
                  ${text.toFixed(2)}
                </span>
              ),
            },
          ]}
          dataSource={symbolTableData}
          pagination={false}
          locale={{ emptyText: '暂无数据' }}
        />
      </Card>

      {/* 胜负分布 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          <Card title="胜负分布">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={[
                    { name: '赢利', value: wins },
                    { name: '亏损', value: losses },
                  ]}
                  cx="50%"
                  cy="50%"
                  label
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  <Cell fill="#52c41a" />
                  <Cell fill="#ff4d4f" />
                </Pie>
                <ChartTooltip />
              </PieChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="风险指标">
            <div style={{ padding: '20px 0' }}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>胜率进度</span>
                  <span>{win_rate.toFixed(1)}%</span>
                </div>
                <Progress percent={win_rate} strokeColor={win_rate >= 50 ? '#52c41a' : '#ff4d4f'} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>最小置信度</span>
                  <span>{settings.min_confidence * 100}%</span>
                </div>
                <Progress percent={settings.min_confidence * 100} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>止损比例</span>
                  <span>{(settings.stop_loss_pct * 100).toFixed(2)}%</span>
                </div>
                <Progress percent={Math.min(settings.stop_loss_pct * 100 * 10, 100)} strokeColor="#ff7a45" />
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span>止盈比例</span>
                  <span>{(settings.take_profit_pct * 100).toFixed(2)}%</span>
                </div>
                <Progress percent={Math.min(settings.take_profit_pct * 100 * 10, 100)} strokeColor="#1890ff" />
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

// 需要导入 BarChart
import { BarChart, Bar } from 'recharts';

export default PerformanceDashboard;
