import { Routes, Route } from 'react-router-dom';
import { FileUpload } from './components/FileUpload';
import WrappedGraphComponent from './components/GraphComponent';
import { ToastProvider } from "@/components/ui/toast"

export default function App() {
  return (
    <ToastProvider>
      <Routes>
        <Route path="/" element={<FileUpload />} />
        <Route path="/graph/:projectId" element={<WrappedGraphComponent />} />
      </Routes>
    </ToastProvider>
  );
}