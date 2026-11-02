CREATE TABLE categories (id integer PRIMARY KEY, name text NOT NULL UNIQUE);
CREATE TABLE customers (
 id integer PRIMARY KEY, name text NOT NULL, segment text NOT NULL,
 region text NOT NULL, created_at date NOT NULL
);
CREATE TABLE products (
 id integer PRIMARY KEY, category_id integer NOT NULL REFERENCES categories,
 name text NOT NULL, price numeric(12,2) NOT NULL CHECK(price>0)
);
CREATE TABLE orders (
 id integer PRIMARY KEY, customer_id integer NOT NULL REFERENCES customers,
 ordered_at date NOT NULL, status text NOT NULL CHECK(status IN ('completed','cancelled'))
);
CREATE TABLE order_items (
 order_id integer REFERENCES orders, product_id integer REFERENCES products,
 quantity integer NOT NULL CHECK(quantity>0), unit_price numeric(12,2) NOT NULL,
 PRIMARY KEY(order_id,product_id)
);
CREATE TABLE payments (
 id integer PRIMARY KEY, order_id integer NOT NULL UNIQUE REFERENCES orders,
 amount numeric(12,2) NOT NULL, paid_at date NOT NULL
);
COMMENT ON TABLE orders IS 'Synthetic orders. Revenue excludes cancelled orders; use order_items.';
INSERT INTO categories VALUES (1,'Electronics'),(2,'Office'),(3,'Home');
INSERT INTO customers
SELECT i, 'Customer '||i,
 (ARRAY['Consumer','Business','Enterprise'])[1+(i-1)%3],
 (ARRAY['North','South','East','West'])[1+(i-1)%4], DATE '2024-01-01'+i
FROM generate_series(1,60) i;
INSERT INTO products
SELECT i, 1+(i-1)%3, 'Product '||lpad(i::text,2,'0'), (i*10)::numeric
FROM generate_series(1,12) i;
-- Fixed dates keep test expectations reproducible, independently of today's date.
INSERT INTO orders
SELECT i, 1+(i-1)%60, DATE '2025-01-01'+((i-1)%365),
 CASE WHEN i%10=0 THEN 'cancelled' ELSE 'completed' END
FROM generate_series(1,720) i;
INSERT INTO order_items
SELECT o.id, 1+(o.id-1)%12, 1+(o.id%3), p.price
FROM orders o JOIN products p ON p.id=1+(o.id-1)%12;
INSERT INTO order_items
SELECT o.id, 1+(o.id+4)%12, 1, p.price
FROM orders o JOIN products p ON p.id=1+(o.id+4)%12;
INSERT INTO payments
SELECT o.id,o.id,sum(i.quantity*i.unit_price),o.ordered_at+1
FROM orders o JOIN order_items i ON i.order_id=o.id
WHERE o.status='completed' GROUP BY o.id;
CREATE INDEX orders_customer_date_idx ON orders(customer_id,ordered_at);
CREATE INDEX orders_date_idx ON orders(ordered_at);
CREATE INDEX items_product_idx ON order_items(product_id);
ANALYZE;
