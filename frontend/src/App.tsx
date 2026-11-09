import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Overview } from './pages/Overview'
import { LiveMonitoring } from './pages/LiveMonitoring'
import { Alerts } from './pages/Alerts'
import { History } from './pages/History'
import { Configuration } from './pages/Configuration'
import { Performance } from './pages/Performance'
import './styles.css'

export function App() { return <BrowserRouter><Routes><Route element={<Layout/>}><Route index element={<Overview/>}/><Route path="live" element={<LiveMonitoring/>}/><Route path="alerts" element={<Alerts/>}/><Route path="history" element={<History/>}/><Route path="configuration" element={<Configuration/>}/><Route path="performance" element={<Performance/>}/></Route></Routes></BrowserRouter> }
