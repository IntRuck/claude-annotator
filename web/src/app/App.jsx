import { BrowserRouter, Route, Routes } from 'react-router-dom';
import QueryProvider from '@/app/QueryProvider';
import ProjectsPage from '@/pages/ProjectsPage';
import WorkspacePage from '@/pages/WorkspacePage';

export default function App() {
  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<WorkspacePage />} />
        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}
