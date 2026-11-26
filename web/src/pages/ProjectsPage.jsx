import { ProjectsHome } from '@/features/projects';
import { ThemeSwitch } from '@/features/theme';
import './pages.css';

export default function ProjectsPage() {
  return (
    <div className="home">
      <header className="home-bar">
        <h1>Claude Annotator</h1>
        <ThemeSwitch />
      </header>
      <main className="home-main">
        <ProjectsHome />
      </main>
    </div>
  );
}
