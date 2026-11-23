import { BrowserRouter, Route, Routes } from 'react-router-dom';
import QueryProvider from '@/app/QueryProvider';
import ProjectsPage from '@/pages/ProjectsPage';

export default function App() {
  return (
    <QueryProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
        </Routes>
      </BrowserRouter>
    </QueryProvider>
  );
}
