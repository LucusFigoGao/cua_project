import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from 'react-router-dom';
import { StoreProvider } from './context/StoreContext';
import { ToastProvider } from './context/ToastContext';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Contacts from './pages/Contacts';
import Companies from './pages/Companies';
import Deals from './pages/Deals';
import Tickets from './pages/Tickets';
import Tasks from './pages/Tasks';
import { Templates, Meetings, Forms } from './pages/Marketing';
import Go from './pages/Go';

function RedirectWithQuery({ to }) {
  const [searchParams] = useSearchParams();
  const query = searchParams.toString();
  return <Navigate to={query ? `${to}?${query}` : to} replace />;
}

function App() {
  return (
    <StoreProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="contacts" element={<Contacts />} />
              <Route path="companies" element={<Companies />} />
              <Route path="deals" element={<Deals />} />
              <Route path="tickets" element={<Tickets />} />
              <Route path="tasks" element={<Tasks />} />
              <Route path="templates" element={<Templates />} />
              <Route path="meetings" element={<Meetings />} />
              <Route path="forms" element={<Forms />} />
              <Route path="go" element={<Go />} />
              <Route path="*" element={<RedirectWithQuery to="/" />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </StoreProvider>
  );
}

export default App;
