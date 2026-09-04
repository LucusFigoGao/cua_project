import React from 'react';
import Header from '../components/Header';

const SERVICES = [
  {
    category: '进站服务',
    items: [
      { name: '自助取票', desc: '凭身份证在自助取票机上快速取票' },
      { name: '人工售票', desc: '车站窗口提供购票、改签、退票等服务' },
      { name: '安检进站', desc: '请提前30分钟到达车站通过安检' },
      { name: '实名验证', desc: '持有效身份证件在闸机处验票进站' },
    ],
  },
  {
    category: '站内服务',
    items: [
      { name: '候车室', desc: '提供普通候车室和VIP商务候车室' },
      { name: '无障碍设施', desc: '配备轮椅坡道、无障碍卫生间、盲道等设施' },
      { name: '母婴室', desc: '大型车站设有母婴候车专区' },
      { name: '行李寄存', desc: '车站提供行李临时寄存服务' },
      { name: '充电服务', desc: '候车区域提供免费充电设施' },
    ],
  },
  {
    category: '列车服务',
    items: [
      { name: '餐车服务', desc: '高铁/动车组设有餐车，提供餐食和饮品' },
      { name: '列车WiFi', desc: '部分高铁列车提供免费WiFi服务' },
      { name: '座位调整', desc: '列车运行中可向乘务员申请座位调换' },
      { name: '应急服务', desc: '车上配备急救药品和医疗设备' },
    ],
  },
  {
    category: '出站服务',
    items: [
      { name: '出站引导', desc: '车站出口设有地铁、公交、出租车指引标识' },
      { name: '接驳服务', desc: '部分车站提供机场大巴、城市公交接驳' },
      { name: '遗失物品', desc: '出站后发现遗失物品可联系12306客服' },
    ],
  },
];

export default function StationServicesPage() {
  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header />
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '20px' }}>
        <div style={{ background: 'white', borderRadius: 8, boxShadow: '0 1px 4px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
          <div style={{ background: 'var(--primary-blue)', color: 'white', padding: '20px 24px' }}>
            <h2 style={{ margin: 0, fontSize: 20 }}>站车服务</h2>
            <div style={{ fontSize: 13, opacity: 0.85, marginTop: 4 }}>了解车站与列车上的各项便民服务</div>
          </div>

          <div style={{ padding: '16px 24px' }}>
            {SERVICES.map((section) => (
              <div key={section.category} style={{ marginBottom: 24 }}>
                <h3 style={{ fontSize: 16, color: 'var(--primary-blue)', borderBottom: '2px solid var(--primary-blue)', paddingBottom: 8, marginBottom: 12 }}>{section.category}</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  {section.items.map((item) => (
                    <div key={item.name} style={{ border: '1px solid #e8e8e8', borderRadius: 6, padding: '14px 16px' }}>
                      <div style={{ fontWeight: 'bold', fontSize: 15 }}>{item.name}</div>
                      <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>{item.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
