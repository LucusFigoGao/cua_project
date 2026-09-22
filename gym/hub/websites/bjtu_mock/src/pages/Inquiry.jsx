import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { INQUIRY_CATEGORIES } from '../data/seed';
import Breadcrumb from '../components/Breadcrumb';

export default function Inquiry() {
  const { state, addInquiry, showToast } = useApp();
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState('form');
  const [form, setForm] = useState({ name: state.currentUser.name, contact: state.currentUser.phone, category: '本科招生', message: '' });
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const cat = searchParams.get('cat');
    if (cat && INQUIRY_CATEGORIES.includes(cat)) {
      setForm((f) => ({ ...f, category: cat }));
    }
  }, [searchParams]);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const validate = () => {
    const errs = {};
    if (!form.name.trim()) errs.name = '请填写姓名';
    const contact = form.contact.trim();
    if (!/^1\d{10}$/.test(contact) && !/^[\w.+-]+@[\w-]+\.[\w.]+$/.test(contact)) {
      errs.contact = '联系方式须为11位手机号或有效邮箱';
    }
    if (form.message.trim().length < 10) errs.message = '咨询内容不少于10字';
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
    addInquiry({
      name: form.name.trim(),
      contact: form.contact.trim(),
      category: form.category,
      message: form.message.trim(),
    });
    showToast('提交成功', 'success');
    setForm((f) => ({ ...f, message: '' }));
    setTab('mine');
  };

  const inquiries = state.inquiries;

  return (
    <div className="service-page">
      <Breadcrumb items={[{ label: '招生就业', to: '/admission/bkzs' }, { label: '招生咨询' }]} />
      <div className="wrap service-wrap">
        <div className="sec-title list-title">
          <h2>招生咨询<span className="sec-en">ADMISSION INQUIRY</span></h2>
        </div>
        <div className="service-tabs">
          <button type="button" className={`service-tab ${tab === 'form' ? 'active' : ''}`} onClick={() => setTab('form')}>我要咨询</button>
          <button type="button" className={`service-tab ${tab === 'mine' ? 'active' : ''}`} onClick={() => setTab('mine')}>我的咨询</button>
        </div>

        {tab === 'form' ? (
          <form className="form-card wide" onSubmit={submit} noValidate>
            <div className="form-row-inline">
              <div className="form-row">
                <label className="form-label">姓名<span className="req">*</span></label>
                <input type="text" value={form.name} onChange={(e) => set('name', e.target.value)} className={errors.name ? 'input-error' : ''} />
                {errors.name && <span className="form-err">{errors.name}</span>}
              </div>
              <div className="form-row">
                <label className="form-label">联系方式<span className="req">*</span></label>
                <input type="text" value={form.contact} onChange={(e) => set('contact', e.target.value)} className={errors.contact ? 'input-error' : ''} placeholder="手机号或邮箱" />
                {errors.contact && <span className="form-err">{errors.contact}</span>}
              </div>
              <div className="form-row">
                <label className="form-label">咨询类别</label>
                <select value={form.category} onChange={(e) => set('category', e.target.value)}>
                  {INQUIRY_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
            </div>
            <div className="form-row">
              <label className="form-label">咨询内容<span className="req">*</span>（不少于10字）</label>
              <textarea rows="5" value={form.message} onChange={(e) => set('message', e.target.value)} className={errors.message ? 'input-error' : ''} placeholder="请描述您想咨询的问题……" />
              <div className="counter-line">
                {errors.message && <span className="form-err">{errors.message}</span>}
                <span className="char-counter">{form.message.length} 字</span>
              </div>
            </div>
            <div className="form-actions">
              <button type="submit" className="btn-primary">提交咨询</button>
              <button type="button" className="btn-ghost" onClick={() => { setForm({ name: '', contact: '', category: '本科招生', message: '' }); setErrors({}); }}>清空重填</button>
            </div>
          </form>
        ) : (
          <div className="mine-block">
            {inquiries.length === 0 ? (
              <div className="empty-state">
                <p>暂无咨询记录</p>
                <button type="button" className="btn-primary" onClick={() => setTab('form')}>去咨询</button>
              </div>
            ) : (
              <div className="inquiry-cards">
                {inquiries.map((q) => (
                  <div className="inquiry-card" key={q.id}>
                    <div className="inquiry-head">
                      <span className={`cat-tag ${q.category === '意见建议' ? 'gold' : 'blue'}`}>{q.category}</span>
                      <span className="muted">{q.submittedAt.slice(0, 16).replace('T', ' ')}</span>
                      <span className={`status-tag ${q.status === '已回复' ? 'ok' : 'wait'}`}>{q.status}</span>
                    </div>
                    <p className="inquiry-msg">{q.message}</p>
                    {q.reply && <div className="inquiry-reply">回复：{q.reply}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
