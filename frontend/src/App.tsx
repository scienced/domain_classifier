/**
 * Main App component with routing
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ChakraProvider } from '@chakra-ui/react'
import { useState } from 'react'

import { apiClient } from './services/api'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import NewRunPage from './pages/NewRunPage'
import RunDetailPage from './pages/RunDetailPage'
import ResultsPage from './pages/ResultsPage'
import ApiUsagePage from './pages/ApiUsagePage'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(apiClient.isAuthenticated())

  const handleLogin = () => {
    setIsAuthenticated(true)
  }

  const handleLogout = () => {
    apiClient.logout()
    setIsAuthenticated(false)
  }

  return (
    <ChakraProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              isAuthenticated ? <Navigate to="/" /> : <LoginPage onLogin={handleLogin} />
            }
          />
          <Route
            path="/"
            element={
              isAuthenticated ? <DashboardPage onLogout={handleLogout} /> : <Navigate to="/login" />
            }
          />
          <Route
            path="/runs/new"
            element={
              isAuthenticated ? <NewRunPage onLogout={handleLogout} /> : <Navigate to="/login" />
            }
          />
          <Route
            path="/runs/:id"
            element={
              isAuthenticated ? <RunDetailPage onLogout={handleLogout} /> : <Navigate to="/login" />
            }
          />
          <Route
            path="/runs/:id/results"
            element={
              isAuthenticated ? <ResultsPage onLogout={handleLogout} /> : <Navigate to="/login" />
            }
          />
          <Route
            path="/api-usage"
            element={
              isAuthenticated ? <ApiUsagePage onLogout={handleLogout} /> : <Navigate to="/login" />
            }
          />
        </Routes>
      </BrowserRouter>
    </ChakraProvider>
  )
}

export default App
