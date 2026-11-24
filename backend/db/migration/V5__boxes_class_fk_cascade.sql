-- Deleting a project failed when it had boxes: the delete cascades to the project's classes, but each box's
-- link to its class (project_id, class_index) had no ON DELETE rule, so it blocked the class delete.
-- Classes are never deleted on their own (an index never changes), so this only cascades with the project.

alter table boxes drop constraint boxes_project_id_class_index_fkey;

alter table boxes add constraint boxes_project_id_class_index_fkey
    foreign key (project_id, class_index) references classes (project_id, class_index) on delete cascade;
