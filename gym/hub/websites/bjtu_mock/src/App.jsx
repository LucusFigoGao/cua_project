import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useSearchParams, useLocation, useNavigate, Outlet } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { getSessionId } from './utils/dataManager';
import Header from './components/Header';
import Footer from './components/Footer';
import BackToTop from './components/BackToTop';
import Home from './pages/Home';
import NewsList from './pages/NewsList';
import NewsDetail from './pages/NewsDetail';
import NoticeList from './pages/NoticeList';
import NoticeDetail from './pages/NoticeDetail';
import Visit from './pages/Visit';
import Inquiry from './pages/Inquiry';
import SearchPage from './pages/SearchPage';
import Favorites from './pages/Favorites';
import About from './pages/About';
import Schools from './pages/Schools';
import SchoolDetail from './pages/SchoolDetail';
import Education from './pages/Education';
import Research from './pages/Research';
import Admission from './pages/Admission';
import En from './pages/En';
import NotFound from './pages/NotFound';
import Go from './pages/Go';

function RedirectWithQuery({ to }) {
  const [searchParams] = useSearchParams();
  const query = searchParams.toString();
  return <Navigate to={query ? `${to}?${query}` : to} replace />;
}

function ScrollToTop() {
  const { pathname, search } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname, search]);
  return null;
}

// Safety net: if a client-side navigation drops ?sid= from the URL (e.g. plain
// <Link to="/notices?category=X">), re-append it via a history replace so the
// visible URL always round-trips the session.
function PreserveSid() {
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('sid')) return;
    const sid = getSessionId();
    if (!sid) return;
    params.set('sid', sid);
    navigate(
      { pathname: location.pathname, search: `?${params.toString()}`, hash: location.hash },
      { replace: true },
    );
  }, [location, navigate]);
  return null;
}

function MainLayout() {
  return (
    <div className="app-shell">
      <Header />
      <main className="app-main">
        <Outlet />
      </main>
      <Footer />
      <BackToTop />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <ScrollToTop />
        <PreserveSid />
        <Routes>
          <Route path="/go" element={<Go />} />
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Home />} />
            <Route path="news" element={<NewsList />} />
            <Route path="news/:id" element={<NewsDetail />} />
            <Route path="notices" element={<NoticeList />} />
            <Route path="notices/:id" element={<NoticeDetail />} />
            <Route path="about" element={<RedirectWithQuery to="/about/jianjie" />} />
            <Route path="about/:section" element={<About />} />
            <Route path="schools" element={<Schools />} />
            <Route path="schools/:id" element={<SchoolDetail />} />
            <Route path="education" element={<RedirectWithQuery to="/education/benke" />} />
            <Route path="education/:section" element={<Education />} />
            <Route path="research" element={<RedirectWithQuery to="/research/dongtai" />} />
            <Route path="research/:section" element={<Research />} />
            <Route path="admission/inquiry" element={<Inquiry />} />
            <Route path="admission" element={<RedirectWithQuery to="/admission/bkzs" />} />
            <Route path="admission/:section" element={<Admission />} />
            <Route path="visit" element={<Visit />} />
            <Route path="search" element={<SearchPage />} />
            <Route path="favorites" element={<Favorites />} />
            <Route path="en" element={<En />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AppProvider>
    </BrowserRouter>
  );
}
