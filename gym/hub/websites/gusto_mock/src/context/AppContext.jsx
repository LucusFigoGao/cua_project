import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { getSessionId, fetchCustomState, initializeData, loadInitialState, saveState, saveInitialState, syncToServer, initialKey } from '../utils/dataManager'

const AppContext = createContext(null)

export const AppProvider = ({ children }) => {
  const [state, setState] = useState(null)
  const [initialState, setInitialState] = useState(null)
  const [sid, setSid] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const sessionId = getSessionId()
    setSid(sessionId)

    const isRefresh = localStorage.getItem(initialKey(sessionId)) !== null

    if (isRefresh) {
      const data = initializeData(sessionId)
      const init = loadInitialState(sessionId) || data
      setState(data)
      setInitialState(init)
      setLoading(false)
      syncToServer(data, sessionId)
    } else {
      fetchCustomState(sessionId).then(custom => {
        const data = initializeData(sessionId, custom)
        const init = loadInitialState(sessionId) || data
        setState(data)
        setInitialState(init)
        setLoading(false)
        // on first load, save as initial and sync
        if (!loadInitialState(sessionId)) {
          saveInitialState(data, sessionId)
          setInitialState(data)
        }
        syncToServer(data, sessionId)
        // Also set on server
        const useSid = sessionId || 'main'
        fetch(`/post?sid=${useSid}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'set', state: data })
        }).catch(() => {})
      })
    }
  }, [])

  const updateState = useCallback((updater) => {
    setState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : { ...prev, ...updater }
      saveState(next, sid)
      syncToServer(next, sid)
      return next
    })
  }, [sid])

  const resetState = useCallback(() => {
    const init = loadInitialState(sid)
    if (init) {
      setState(init)
      saveState(init, sid)
      syncToServer(init, sid)
    }
  }, [sid])

  // Employee operations
  const updateEmployee = useCallback((employeeId, updates) => {
    updateState(prev => ({
      ...prev,
      employees: prev.employees.map(emp =>
        emp.id === employeeId ? { ...emp, ...updates } : emp
      )
    }))
  }, [updateState])

  const addEmployee = useCallback((employee) => {
    updateState(prev => ({
      ...prev,
      employees: [...prev.employees, employee]
    }))
  }, [updateState])

  // Payroll operations
  const updatePayroll = useCallback((payrollId, updates) => {
    updateState(prev => ({
      ...prev,
      payrolls: prev.payrolls.map(p =>
        p.id === payrollId ? { ...p, ...updates } : p
      )
    }))
  }, [updateState])

  const addPayroll = useCallback((payroll) => {
    updateState(prev => ({
      ...prev,
      payrolls: [payroll, ...prev.payrolls]
    }))
  }, [updateState])

  // Time off operations
  const approveTimeOff = useCallback((requestId) => {
    updateState(prev => {
      const request = prev.timeOffRequests.find(r => r.id === requestId)
      if (!request) return prev

      const updatedRequests = prev.timeOffRequests.map(r =>
        r.id === requestId
          ? { ...r, status: 'Approved', reviewedBy: 'emp_1', reviewedAt: new Date().toISOString() }
          : r
      )

      // Deduct hours from employee balance
      const updatedEmployees = prev.employees.map(emp => {
        if (emp.id !== request.employeeId) return emp
        const pto = { ...emp.pto }
        if (request.type === 'Vacation') {
          pto.vacationBalance = Math.max(0, pto.vacationBalance - request.totalHours)
        } else if (request.type === 'Sick') {
          pto.sickBalance = Math.max(0, pto.sickBalance - request.totalHours)
        }
        return { ...emp, pto }
      })

      return {
        ...prev,
        timeOffRequests: updatedRequests,
        employees: updatedEmployees
      }
    })
  }, [updateState])

  const denyTimeOff = useCallback((requestId) => {
    updateState(prev => ({
      ...prev,
      timeOffRequests: prev.timeOffRequests.map(r =>
        r.id === requestId
          ? { ...r, status: 'Denied', reviewedBy: 'emp_1', reviewedAt: new Date().toISOString() }
          : r
      )
    }))
  }, [updateState])

  // Time entry operations
  const approveTimeEntry = useCallback((entryId) => {
    updateState(prev => ({
      ...prev,
      timeEntries: prev.timeEntries.map(te =>
        te.id === entryId ? { ...te, status: 'Approved' } : te
      )
    }))
  }, [updateState])

  const updateTimeEntry = useCallback((entryId, updates) => {
    updateState(prev => ({
      ...prev,
      timeEntries: prev.timeEntries.map(te =>
        te.id === entryId ? { ...te, ...updates } : te
      )
    }))
  }, [updateState])

  // Todo operations
  const completeTodo = useCallback((todoId) => {
    updateState(prev => ({
      ...prev,
      todoItems: prev.todoItems.map(t =>
        t.id === todoId ? { ...t, status: 'completed' } : t
      )
    }))
  }, [updateState])

  // Notification operations
  const markNotificationRead = useCallback((notifId) => {
    updateState(prev => ({
      ...prev,
      notifications: prev.notifications.map(n =>
        n.id === notifId ? { ...n, read: true } : n
      )
    }))
  }, [updateState])

  const markAllNotificationsRead = useCallback(() => {
    updateState(prev => ({
      ...prev,
      notifications: prev.notifications.map(n => ({ ...n, read: true }))
    }))
  }, [updateState])

  // Document operations
  const addDocument = useCallback((doc) => {
    updateState(prev => ({
      ...prev,
      documents: [...prev.documents, doc]
    }))
  }, [updateState])

  // Report history operations
  const addReportHistory = useCallback((reportType, action) => {
    updateState(prev => ({
      ...prev,
      reportHistory: [
        ...(prev.reportHistory || []),
        { reportType, action, timestamp: new Date().toISOString() }
      ]
    }))
  }, [updateState])

  // Onboarding checklist operations
  const completeOnboardingTask = useCallback((checklistId, taskId) => {
    updateState(prev => ({
      ...prev,
      onboardingChecklists: prev.onboardingChecklists.map(cl =>
        cl.id === checklistId
          ? {
              ...cl,
              tasks: cl.tasks.map(t =>
                t.id === taskId
                  ? { ...t, status: t.status === 'completed' ? 'pending' : 'completed', completedDate: t.status === 'completed' ? null : new Date().toISOString().split('T')[0] }
                  : t
              )
            }
          : cl
      )
    }))
  }, [updateState])

  // Time off request creation
  const addTimeOffRequest = useCallback((request) => {
    updateState(prev => ({
      ...prev,
      timeOffRequests: [...(prev.timeOffRequests || []), request]
    }))
  }, [updateState])

  const value = {
    state,
    sid,
    loading,
    initialState,
    updateState,
    resetState,
    updateEmployee,
    addEmployee,
    updatePayroll,
    addPayroll,
    approveTimeOff,
    denyTimeOff,
    approveTimeEntry,
    updateTimeEntry,
    completeTodo,
    markNotificationRead,
    markAllNotificationsRead,
    addDocument,
    addReportHistory,
    completeOnboardingTask,
    addTimeOffRequest
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'var(--font)', color: '#666' }}>
        Loading...
      </div>
    )
  }

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  )
}

export const useAppContext = () => {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useAppContext must be used within AppProvider')
  return ctx
}

export default AppContext
