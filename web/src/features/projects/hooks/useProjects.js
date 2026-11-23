import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/queryKeys';
import { createProject, getProject, listProjects } from '../api/projectsApi';

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects(), queryFn: listProjects });
}

export function useProject(projectId) {
  return useQuery({ queryKey: queryKeys.project(projectId), queryFn: () => getProject(projectId) });
}

export function useCreateProject() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (name) => createProject(name),
    onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.projects(), exact: true }),
  });
}
