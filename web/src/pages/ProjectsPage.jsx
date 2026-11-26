import { ProjectsHome } from '@/features/projects';
import './pages.css';

export default function ProjectsPage() {
  return (
    <div className="home">
      <header className="home-bar">
        <h1>Claude Annotator</h1>
      </header>
      <main className="home-main">
        <ProjectsHome />
      </main>
    </div>
  );
}
