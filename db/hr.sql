CREATE TABLE departments (id integer PRIMARY KEY, name text NOT NULL UNIQUE);
CREATE TABLE positions (id integer PRIMARY KEY, title text NOT NULL, level integer NOT NULL);
CREATE TABLE employees (
 id integer PRIMARY KEY, name text NOT NULL, department_id integer NOT NULL REFERENCES departments,
 position_id integer NOT NULL REFERENCES positions, hired_at date NOT NULL, terminated_at date
);
CREATE TABLE salaries (
 employee_id integer REFERENCES employees, effective_from date NOT NULL,
 annual_amount numeric(12,2) NOT NULL, PRIMARY KEY(employee_id,effective_from)
);
CREATE TABLE attendance (
 employee_id integer REFERENCES employees, attended_on date NOT NULL,
 hours numeric(4,1) NOT NULL, PRIMARY KEY(employee_id,attended_on)
);
CREATE TABLE performance_reviews (
 employee_id integer REFERENCES employees, reviewed_on date NOT NULL,
 score integer NOT NULL CHECK(score BETWEEN 1 AND 5), PRIMARY KEY(employee_id,reviewed_on)
);
COMMENT ON TABLE salaries IS 'Annual USD salary history; choose latest effective_from per employee.';
INSERT INTO departments VALUES (1,'Engineering'),(2,'Sales'),(3,'People'),(4,'Operations');
INSERT INTO positions VALUES (1,'Associate',1),(2,'Specialist',2),(3,'Senior',3),(4,'Lead',4);
INSERT INTO employees
SELECT i,'Employee '||i,1+(i-1)%4,1+(i-1)%4,DATE '2020-01-01'+i*10,
 CASE WHEN i%8=0 THEN DATE '2025-10-01' END
FROM generate_series(1,80) i;
INSERT INTO salaries
SELECT i,DATE '2024-01-01',40000+i*1000 FROM generate_series(1,80) i;
INSERT INTO salaries
SELECT i,DATE '2025-01-01',42000+i*1000 FROM generate_series(1,80) i;
INSERT INTO attendance
SELECT i,DATE '2025-09-01'+d,CASE WHEN (i+d)%7=0 THEN 0 ELSE 8 END
FROM generate_series(1,80) i CROSS JOIN generate_series(0,29) d;
INSERT INTO performance_reviews
SELECT i,DATE '2025-06-30',1+(i-1)%5 FROM generate_series(1,80) i;
CREATE INDEX employees_department_idx ON employees(department_id);
CREATE INDEX attendance_date_idx ON attendance(attended_on);
ANALYZE;
