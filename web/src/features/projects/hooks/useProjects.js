import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import {
  createProject, deleteProject, getProject, listProjects, listProjectSummaries, updateProject,
} from '../api/projectsApi';

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects(), queryFn: listProjects });
}

/** Projects with their numbers, for the projects page. */
export function useProjectSummaries() {
  return useQuery({ queryKey: queryKeys.projectSummaries(), queryFn: listProjectSummaries });
}

export function useProject(projectId) {
  return useQuery({ queryKey: queryKeys.project(projectId), queryFn: () => getProject(projectId) });
}

/** Both project lists (plain and with numbers) refetch after a change. */
function refreshLists(client) {
  return Promise.all([
    client.invalidateQueries({ queryKey: queryKeys.projects(), exact: true }),
    client.invalidateQueries({ queryKey: queryKeys.projectSummaries() }),
  ]);
}

/** mutate({ name, description }) */
export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fields) => createProject(fields),
    onSuccess: () => refreshLists(client),
  });
}

/** mutate({ projectId, name?, description? }) */
export function useUpdateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, ...patch }) => updateProject(projectId, patch),
    onSuccess: (project) => {
      client.setQueryData(queryKeys.project(project.id), project);
      return refreshLists(client);
    },
  });
}

/** mutate(projectId). Also drops everything cached for that project. */
export function useDeleteProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (projectId) => deleteProject(projectId),
    onSuccess: (_, projectId) => {
      client.removeQueries({ queryKey: queryKeys.project(projectId) });
      return refreshLists(client);
    },
  });
}
