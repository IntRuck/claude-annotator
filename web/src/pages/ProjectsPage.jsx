import { ProjectList } from '@/features/projects';
import './pages.css';

export default function ProjectsPage() {
  return (
    <main className="page">
      <h1>Claude Annotator</h1>
      <ProjectList />
    </main>
  );
}
