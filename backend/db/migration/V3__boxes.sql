-- Boxes on images. Corners are fractions of the image size (0-1), like today's normalised YOLO labels.
-- A box always points at one of its project's classes (YOLO class ID = class_index).

create table boxes (
    id          bigint generated always as identity primary key,
    image_id    bigint           not null references images (id) on delete cascade,
    project_id  bigint           not null,
    class_index integer          not null,
    x1          double precision not null,
    y1          double precision not null,
    x2          double precision not null,
    y2          double precision not null,
    conf        real,
    source      text             not null check (source in ('ai', 'human', 'import')),
    foreign key (project_id, class_index) references classes (project_id, class_index),
    check (x1 >= 0 and x1 < x2 and x2 <= 1 and y1 >= 0 and y1 < y2 and y2 <= 1)
);

create index boxes_image on boxes (image_id);
create index boxes_project_class on boxes (project_id, class_index);

alter table boxes enable row level security;

-- images.box_count follows the boxes table, however boxes are written.
create function boxes_keep_image_count() returns trigger
    language plpgsql as
$$
begin
    if tg_op = 'INSERT' then
        update images set box_count = box_count + 1 where id = new.image_id;
    elsif tg_op = 'DELETE' then
        update images set box_count = box_count - 1 where id = old.image_id;
    end if;
    return null;
end;
$$;

create trigger boxes_count_after_change
    after insert or delete on boxes
    for each row execute function boxes_keep_image_count();
