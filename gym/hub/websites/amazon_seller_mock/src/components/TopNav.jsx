import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Menu, Search, Bell, Mail, Settings, HelpCircle, ChevronDown, X, AlertTriangle, CheckCircle, Info, AlertCircle } from 'lucide-react';
import { useApp } from '../context/AppContext';

function NotificationIcon({ type }) {
  const props = { size: 16 };
  if (type === 'warning') return <AlertTriangle {...props} style={{ color: '#b7791f' }} />;
  if (type === 'error') return <AlertCircle {...props} style={{ color: '#d13212' }} />;
  if (type === 'success') return <CheckCircle {...props} style={{ color: '#067d62' }} />;
  return <Info {...props} style={{ color: '#007185' }} />;
}

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function TopNav({ onHamburger }) {
  const { state, dispatch } = useApp();
  const navigate = useNavigate();
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchVal, setSearchVal] = useState('');
  const notifRef = useRef(null);

  useEffect(() => {
    function handler(e) {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
    }
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (!state) return null;

  const unreadCount = state.seller.notificationCount;
  const unreadMessages = state.seller.unreadMessages;

  const markAllRead = () => dispatch({ type: 'MARK_ALL_NOTIFICATIONS_READ' });
  const markRead = (id) => {
    const notif = state.notifications.find(n => n.id === id);
    dispatch({ type: 'MARK_NOTIFICATION_READ', payload: id });
    if (notif && notif.actionUrl) navigate(notif.actionUrl);
    setNotifOpen(false);
  };

  return (
    <nav style={{ position: 'fixed', top: 0, left: 0, right: 0, height: 50, background: '#232f3e', zIndex: 1000, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 0 }}>
      {/* Left */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <button onClick={onHamburger} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}>
          <Menu size={20} color="white" />
        </button>
        <Link to="/" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', textDecoration: 'none' }}>
          <span style={{ color: 'white', fontSize: 18, fontWeight: 700, letterSpacing: '-0.5px', lineHeight: 1 }}>amazon</span>
          <span style={{ color: '#ff9900', fontSize: 10, lineHeight: 1 }}>seller central</span>
        </Link>
      </div>

      {/* Center: Search */}
      <div style={{ flex: 1, display: 'flex', justifyContent: 'center', padding: '0 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', background: 'white', borderRadius: 4, maxWidth: 400, width: '100%', height: 34 }}>
          <Search size={16} color="#888" style={{ marginLeft: 8, flexShrink: 0 }} />
          <input
            value={searchVal}
            onChange={e => setSearchVal(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && searchVal.trim()) navigate(`/inventory?search=${encodeURIComponent(searchVal.trim())}`) }}
            placeholder="Search Seller Central"
            style={{ border: 'none', outline: 'none', flex: 1, padding: '0 8px', fontSize: 13, height: '100%', borderRadius: 4 }}
          />
        </div>
      </div>

      {/* Right */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexShrink: 0 }}>
        {/* Bell */}
        <div ref={notifRef} style={{ position: 'relative' }}>
          <button onClick={() => setNotifOpen(!notifOpen)} style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Bell size={20} color="white" />
            {unreadCount > 0 && (
              <span style={{ position: 'absolute', top: -6, right: -6, background: '#d13212', color: 'white', fontSize: 10, fontWeight: 700, borderRadius: '50%', minWidth: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px' }}>
                {unreadCount}
              </span>
            )}
          </button>
          {notifOpen && (
            <div style={{ position: 'absolute', top: 36, right: 0, width: 320, maxHeight: 400, overflowY: 'auto', background: 'white', border: '1px solid #ddd', borderRadius: 4, boxShadow: '0 2px 8px rgba(0,0,0,0.15)', zIndex: 200 }}>
              <div style={{ padding: '8px 12px', borderBottom: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, fontWeight: 700 }}>Notifications</span>
                <button onClick={markAllRead} className="btn-link" style={{ fontSize: 12 }}>Mark all read</button>
              </div>
              {state.notifications.map(n => (
                <div key={n.id} onClick={() => markRead(n.id)} style={{ padding: '10px 12px', borderBottom: '1px solid #f0f0f0', cursor: 'pointer', display: 'flex', gap: 8, background: n.isRead ? 'white' : '#f9fafb', borderLeft: n.isRead ? 'none' : '3px solid #ff9900' }}>
                  <div style={{ flexShrink: 0, marginTop: 2 }}><NotificationIcon type={n.type} /></div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: n.isRead ? 400 : 700 }}>{n.title}</div>
                    <div style={{ fontSize: 12, color: '#555', lineHeight: '16px', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{n.message}</div>
                    <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{timeAgo(n.timestamp)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* US Flag / locale indicator */}
        <span style={{ color: 'white', fontSize: 13 }}>🇺🇸</span>

        {/* Mail */}
        <button onClick={() => navigate('/messages')} style={{ background: 'none', border: 'none', cursor: 'pointer', position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Mail size={20} color="white" />
          {unreadMessages > 0 && (
            <span style={{ position: 'absolute', top: -6, right: -6, background: '#d13212', color: 'white', fontSize: 10, fontWeight: 700, borderRadius: '50%', minWidth: 16, height: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 3px' }}>
              {unreadMessages}
            </span>
          )}
        </button>

        <button onClick={() => navigate('/settings')} style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
          <Settings size={20} color="white" />
        </button>

        <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'white', fontSize: 13, display: 'flex', alignItems: 'center', gap: 2 }}>
          <HelpCircle size={16} color="white" />
          <span>Help</span>
        </button>

        <span style={{ color: 'white', fontSize: 13, fontWeight: 700, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {state.seller.displayName}
        </span>
      </div>
    </nav>
  );
}
