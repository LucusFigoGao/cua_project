import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import Breadcrumb from '../components/Breadcrumb';
import Modal from '../components/Modal';

const pad2 = (n) => String(n).padStart(2, '0');
const TODAY = (() => {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
})();

const emptyForm = (user) => ({
  visitorName: user.name || '',
  idType: '身份证',
  idNumber: user.idNumber || '',
  phone: user.phone || '',
  visitDate: '',
  timeSlot: '上午',
  campus: '主校区',
  visitorCount: 3,
  purpose: '',
});

export default function Visit() {
  const { state, addBooking, cancelBooking, showToast } = useApp();
  const [tab, setTab] = useState('form');
  const [form, setForm] = useState(() => emptyForm(state.currentUser));
  const [errors, setErrors] = useState({});
  const [cancelId, setCancelId] = useState(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const validate = () => {
    const errs = {};
    if (!form.visitorName.trim()) errs.visitorName = '请填写参观人姓名';
    if (!/^\d{17}[\dXx]$/.test(form.idNumber.trim())) errs.idNumber = '证件号码须为18位（末位可为X）';
    if (!/^1\d{10}$/.test(form.phone.trim())) errs.phone = '联系电话须为11位手机号';
    if (!form.visitDate) errs.visitDate = '请选择参观日期';
    else if (form.visitDate < TODAY) errs.visitDate = '参观日期不能早于今天';
    const count = Number(form.visitorCount);
    if (!Number.isInteger(count) || count < 1 || count > 10) errs.visitorCount = '参观人数须为1-10的整数';
    return errs;
  };

  const submit = (e) => {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      showToast('请检查表单填写内容', 'error');
      return;
    }
    addBooking({
      visitorName: form.visitorName.trim(),
      idType: form.idType,
      idNumber: form.idNumber.trim(),
      phone: form.phone.trim(),
      visitDate: form.visitDate,
      timeSlot: form.timeSlot,
      campus: form.campus,
      visitorCount: Number(form.visitorCount),
      purpose: form.purpose.trim(),
    });
    showToast('预约成功', 'success');
    setForm(emptyForm(state.currentUser));
    setTab('mine');
  };

  const bookings = [...state.bookings].sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  const cancelTarget = bookings.find((b) => b.id === cancelId);

  return (
    <div className="service-page">
      <Breadcrumb items={[{ label: '校园参观预约' }]} />
      <div className="wrap service-wrap">
        <div className="sec-title list-title">
          <h2>校园参观预约<span className="sec-en">CAMPUS VISIT</span></h2>
        </div>
        <div className="service-tabs">
          <button type="button" className={`service-tab ${tab === 'form' ? 'active' : ''}`} onClick={() => setTab('form')}>参观预约</button>
          <button type="button" className={`service-tab ${tab === 'mine' ? 'active' : ''}`} onClick={() => setTab('mine')}>我的预约</button>
        </div>

        {tab === 'form' ? (
          <div className="service-grid">
            <form className="form-card" onSubmit={submit} noValidate>
              <div className="form-row">
                <label className="form-label">参观人姓名<span className="req">*</span></label>
                <input type="text" value={form.visitorName} onChange={(e) => set('visitorName', e.target.value)} className={errors.visitorName ? 'input-error' : ''} />
                {errors.visitorName && <span className="form-err">{errors.visitorName}</span>}
              </div>
              <div className="form-row-inline">
                <div className="form-row">
                  <label className="form-label">证件类型</label>
                  <select value={form.idType} onChange={(e) => set('idType', e.target.value)}>
                    <option>身份证</option>
                    <option>护照</option>
                    <option>军官证</option>
                  </select>
                </div>
                <div className="form-row grow">
                  <label className="form-label">证件号码<span className="req">*</span></label>
                  <input type="text" maxLength={18} value={form.idNumber} onChange={(e) => set('idNumber', e.target.value)} className={errors.idNumber ? 'input-error' : ''} />
                  {errors.idNumber && <span className="form-err">{errors.idNumber}</span>}
                </div>
              </div>
              <div className="form-row">
                <label className="form-label">联系电话<span className="req">*</span></label>
                <input type="text" maxLength={11} value={form.phone} onChange={(e) => set('phone', e.target.value)} className={errors.phone ? 'input-error' : ''} />
                {errors.phone && <span className="form-err">{errors.phone}</span>}
              </div>
              <div className="form-row-inline">
                <div className="form-row">
                  <label className="form-label">参观日期<span className="req">*</span></label>
                  <input type="date" min={TODAY} value={form.visitDate} onChange={(e) => set('visitDate', e.target.value)} className={errors.visitDate ? 'input-error' : ''} />
                  {errors.visitDate && <span className="form-err">{errors.visitDate}</span>}
                </div>
                <div className="form-row">
                  <label className="form-label">时段</label>
                  <div className="radio-line">
                    {['上午', '下午'].map((s) => (
                      <label key={s} className="scope-radio">
                        <input type="radio" name="timeSlot" checked={form.timeSlot === s} onChange={() => set('timeSlot', s)} />
                        <span>{s}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <div className="form-row-inline">
                <div className="form-row">
                  <label className="form-label">校区</label>
                  <select value={form.campus} onChange={(e) => set('campus', e.target.value)}>
                    <option>主校区</option>
                    <option>威海校区</option>
                  </select>
                </div>
                <div className="form-row">
                  <label className="form-label">人数（1-10）</label>
                  <input type="number" min="1" max="10" value={form.visitorCount} onChange={(e) => set('visitorCount', e.target.value)} className={errors.visitorCount ? 'input-error' : ''} />
                  {errors.visitorCount && <span className="form-err">{errors.visitorCount}</span>}
                </div>
              </div>
              <div className="form-row">
                <label className="form-label">参观目的（选填）</label>
                <textarea rows="3" value={form.purpose} onChange={(e) => set('purpose', e.target.value)} placeholder="如：校园参观、校史馆参观等" />
              </div>
              <div className="form-actions">
                <button type="submit" className="btn-primary">提交预约</button>
                <button type="button" className="btn-ghost" onClick={() => { setForm(emptyForm(state.currentUser)); setErrors({}); }}>清空重填</button>
              </div>
            </form>
            <aside className="notice-panel">
              <h3>参观须知</h3>
              <ul>
                <li>开放时间：教学周工作日及周末上午 9:00-11:30、下午 14:00-16:30，法定节假日以通知为准。</li>
                <li>入校须携带预约人有效证件原件，人证一致方可入校。</li>
                <li>团体参观（10人以上）须提前3日向学校办公室备案。</li>
                <li>校园参观为公益活动，不收取任何费用。</li>
                <li>请爱护校园环境与文物建筑，教学区域保持安静。</li>
              </ul>
            </aside>
          </div>
        ) : (
          <div className="mine-block">
            {bookings.length === 0 ? (
              <div className="empty-state">
                <p>暂无预约记录</p>
                <button type="button" className="btn-primary" onClick={() => setTab('form')}>去预约</button>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>预约号</th><th>参观人</th><th>日期</th><th>时段</th><th>校区</th><th>人数</th><th>状态</th><th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.id}>
                      <td className="mono">{b.id}</td>
                      <td>{b.visitorName}</td>
                      <td>{b.visitDate}</td>
                      <td>{b.timeSlot}</td>
                      <td>{b.campus}</td>
                      <td>{b.visitorCount}</td>
                      <td><span className={`status-tag ${b.status === '已预约' ? 'ok' : 'off'}`}>{b.status}</span></td>
                      <td>
                        {b.status === '已预约' && b.visitDate >= TODAY ? (
                          <button type="button" className="btn-danger-ghost" onClick={() => setCancelId(b.id)}>取消预约</button>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {cancelTarget && (
        <Modal
          title="取消预约"
          danger
          confirmText="确认取消"
          onClose={() => setCancelId(null)}
          onConfirm={() => {
            cancelBooking(cancelTarget.id);
            showToast('预约已取消', 'info');
            setCancelId(null);
          }}
        >
          <p>确定要取消预约号为 <strong>{cancelTarget.id}</strong>（{cancelTarget.visitDate} {cancelTarget.timeSlot}）的参观预约吗？取消后名额将释放。</p>
        </Modal>
      )}
    </div>
  );
}
