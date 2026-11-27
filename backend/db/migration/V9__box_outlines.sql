-- Outlines (segmentation): an object can carry an outline, dots as fractions of the image (0-1): [[x, y], ...].
-- null = a plain box. The box columns stay; the backend fills them from the dots.
alter table boxes add column points jsonb;

alter table boxes add constraint boxes_points_shape check (
    points is null or (jsonb_typeof(points) = 'array' and jsonb_array_length(points) between 3 and 1000));
