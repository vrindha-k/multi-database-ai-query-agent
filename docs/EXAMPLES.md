# Verified synthetic-data examples

These results are calculated by PostgreSQL using `scripts/verify_examples.py`.
Dates are fixed in 2025. Revenue is order-item gross revenue for completed orders.
The SQL below is a reproducible reference, not a claim about a live Claude response.

## 1. How many customers are in each segment?

Database: `ecommerce`

```sql
SELECT segment, COUNT(*) AS customers FROM "public".customers GROUP BY segment ORDER BY segment
```

```json
{
  "columns": [
    "segment",
    "customers"
  ],
  "rows": [
    [
      "Business",
      20
    ],
    [
      "Consumer",
      20
    ],
    [
      "Enterprise",
      20
    ]
  ]
}
```

## 2. What is total completed-order revenue in 2025?

Database: `ecommerce`

```sql
SELECT SUM(i.quantity * i.unit_price) AS revenue FROM "public".orders AS o JOIN "public".order_items AS i ON o.id = i.order_id WHERE o.status = 'completed' AND o.ordered_at >= CAST('2025-01-01' AS DATE) AND o.ordered_at < CAST('2026-01-01' AS DATE)
```

```json
{
  "columns": [
    "revenue"
  ],
  "rows": [
    [
      "124560.00"
    ]
  ]
}
```

## 3. Which five products generated the most completed-order revenue?

Database: `ecommerce`

```sql
SELECT p.name, SUM(i.quantity * i.unit_price) AS revenue FROM "public".products AS p JOIN "public".order_items AS i ON i.product_id = p.id JOIN "public".orders AS o ON o.id = i.order_id WHERE o.status = 'completed' GROUP BY p.id, p.name ORDER BY revenue DESC, p.name LIMIT 5
```

```json
{
  "columns": [
    "name",
    "revenue"
  ],
  "rows": [
    [
      "Product 11",
      "25080.00"
    ],
    [
      "Product 08",
      "16320.00"
    ],
    [
      "Product 10",
      "15600.00"
    ],
    [
      "Product 12",
      "12960.00"
    ],
    [
      "Product 07",
      "11760.00"
    ]
  ]
}
```

## 4. How many customers placed more than three completed orders?

Database: `ecommerce`

```sql
SELECT COUNT(*) AS customers FROM (SELECT customer_id FROM "public".orders WHERE status = 'completed' GROUP BY customer_id HAVING COUNT(*) > 3) AS repeat_customers
```

```json
{
  "columns": [
    "customers"
  ],
  "rows": [
    [
      54
    ]
  ]
}
```

## 5. What is average completed-order value by customer segment?

Database: `ecommerce`

```sql
WITH totals AS (SELECT o.id, o.customer_id, SUM(i.quantity * i.unit_price) AS total FROM "public".orders AS o JOIN "public".order_items AS i ON i.order_id = o.id WHERE o.status = 'completed' GROUP BY o.id, o.customer_id) SELECT c.segment, ROUND(CAST(AVG(t.total) AS DECIMAL), 2) AS average_order_value FROM "public".customers AS c JOIN totals AS t ON c.id = t.customer_id GROUP BY c.segment ORDER BY c.segment
```

```json
{
  "columns": [
    "segment",
    "average_order_value"
  ],
  "rows": [
    [
      "Business",
      "256.67"
    ],
    [
      "Consumer",
      "183.33"
    ],
    [
      "Enterprise",
      "136.67"
    ]
  ]
}
```

## 6. Compare completed-order revenue across regions in 2025.

Database: `ecommerce`

```sql
SELECT c.region, SUM(i.quantity * i.unit_price) AS revenue FROM "public".customers AS c JOIN "public".orders AS o ON o.customer_id = c.id JOIN "public".order_items AS i ON i.order_id = o.id WHERE o.status = 'completed' GROUP BY c.region ORDER BY c.region
```

```json
{
  "columns": [
    "region",
    "revenue"
  ],
  "rows": [
    [
      "East",
      "44400.00"
    ],
    [
      "North",
      "26400.00"
    ],
    [
      "South",
      "25440.00"
    ],
    [
      "West",
      "28320.00"
    ]
  ]
}
```

## 7. Show January through March 2025 revenue, previous-month revenue and running totals.

Database: `ecommerce`

```sql
WITH monthly AS (SELECT CAST(DATE_TRUNC('MONTH', o.ordered_at) AS DATE) AS month, SUM(i.quantity * i.unit_price) AS revenue FROM "public".orders AS o JOIN "public".order_items AS i ON i.order_id = o.id WHERE o.status = 'completed' GROUP BY 1) SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) AS previous_revenue, SUM(revenue) OVER (ORDER BY month ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_revenue FROM monthly ORDER BY month LIMIT 3
```

```json
{
  "columns": [
    "month",
    "revenue",
    "previous_revenue",
    "running_revenue"
  ],
  "rows": [
    [
      "2025-01-01",
      "10630.00",
      null,
      "10630.00"
    ],
    [
      "2025-02-01",
      "9880.00",
      "10630.00",
      "20510.00"
    ],
    [
      "2025-03-01",
      "10450.00",
      "9880.00",
      "30960.00"
    ]
  ]
}
```

## 8. Which customers had no completed orders during the 90 days ending December 31, 2025?

Database: `ecommerce`

```sql
SELECT c.id, c.name FROM "public".customers AS c LEFT JOIN "public".orders AS o ON o.customer_id = c.id AND o.status = 'completed' AND o.ordered_at > CAST('2025-12-31' AS DATE) - 90 AND o.ordered_at <= CAST('2025-12-31' AS DATE) WHERE o.id IS NULL ORDER BY c.id
```

```json
{
  "columns": [
    "id",
    "name"
  ],
  "rows": [
    [
      10,
      "Customer 10"
    ],
    [
      20,
      "Customer 20"
    ],
    [
      30,
      "Customer 30"
    ],
    [
      40,
      "Customer 40"
    ],
    [
      50,
      "Customer 50"
    ],
    [
      60,
      "Customer 60"
    ]
  ]
}
```

## 9. What is active headcount by department as of December 31, 2025?

Database: `hr`

```sql
SELECT d.name, COUNT(e.id) AS headcount FROM "public".departments AS d LEFT JOIN "public".employees AS e ON e.department_id = d.id AND e.hired_at <= CAST('2025-12-31' AS DATE) AND (e.terminated_at IS NULL OR e.terminated_at > CAST('2025-12-31' AS DATE)) GROUP BY d.name ORDER BY d.name
```

```json
{
  "columns": [
    "name",
    "headcount"
  ],
  "rows": [
    [
      "Engineering",
      20
    ],
    [
      "Operations",
      10
    ],
    [
      "People",
      20
    ],
    [
      "Sales",
      20
    ]
  ]
}
```

## 10. What is average latest annual salary by department, including former employees?

Database: `hr`

```sql
WITH latest AS (SELECT employee_id, annual_amount, ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY effective_from DESC) AS rn FROM "public".salaries) SELECT d.name, ROUND(CAST(AVG(s.annual_amount) AS DECIMAL), 2) AS average_salary FROM "public".departments AS d JOIN "public".employees AS e ON e.department_id = d.id JOIN latest AS s ON s.employee_id = e.id AND s.rn = 1 GROUP BY d.name ORDER BY d.name
```

```json
{
  "columns": [
    "name",
    "average_salary"
  ],
  "rows": [
    [
      "Engineering",
      "81000.00"
    ],
    [
      "Operations",
      "84000.00"
    ],
    [
      "People",
      "83000.00"
    ],
    [
      "Sales",
      "82000.00"
    ]
  ]
}
```

## 11. Rank departments by average performance score with RANK and DENSE_RANK.

Database: `hr`

```sql
WITH scores AS (SELECT d.name, ROUND(CAST(AVG(r.score) AS DECIMAL), 2) AS score FROM "public".departments AS d JOIN "public".employees AS e ON e.department_id = d.id JOIN "public".performance_reviews AS r ON r.employee_id = e.id GROUP BY d.name) SELECT name, score, RANK() OVER (ORDER BY score DESC) AS rank, DENSE_RANK() OVER (ORDER BY score DESC) AS dense_rank FROM scores ORDER BY name
```

```json
{
  "columns": [
    "name",
    "score",
    "rank",
    "dense_rank"
  ],
  "rows": [
    [
      "Engineering",
      "3.00",
      1,
      1
    ],
    [
      "Operations",
      "3.00",
      1,
      1
    ],
    [
      "People",
      "3.00",
      1,
      1
    ],
    [
      "Sales",
      "3.00",
      1,
      1
    ]
  ]
}
```

## 12. How many attendance hours were recorded per department in September 2025?

Database: `hr`

```sql
SELECT d.name, SUM(a.hours) AS hours FROM "public".departments AS d JOIN "public".employees AS e ON e.department_id = d.id JOIN "public".attendance AS a ON a.employee_id = e.id WHERE a.attended_on >= CAST('2025-09-01' AS DATE) AND a.attended_on < CAST('2025-10-01' AS DATE) GROUP BY d.name ORDER BY d.name
```

```json
{
  "columns": [
    "name",
    "hours"
  ],
  "rows": [
    [
      "Engineering",
      "4112.0"
    ],
    [
      "Operations",
      "4120.0"
    ],
    [
      "People",
      "4120.0"
    ],
    [
      "Sales",
      "4112.0"
    ]
  ]
}
```

## 13. Which department had the most departures during 2025?

Database: `hr`

```sql
SELECT d.name, COUNT(*) AS departures FROM "public".departments AS d JOIN "public".employees AS e ON e.department_id = d.id WHERE e.terminated_at >= CAST('2025-01-01' AS DATE) AND e.terminated_at < CAST('2026-01-01' AS DATE) GROUP BY d.name ORDER BY departures DESC, d.name
```

```json
{
  "columns": [
    "name",
    "departures"
  ],
  "rows": [
    [
      "Operations",
      10
    ]
  ]
}
```

## 14. Show the first three employee salary ranks and next higher salary with LEAD.

Database: `hr`

```sql
SELECT employee_id, annual_amount, ROW_NUMBER() OVER (ORDER BY annual_amount, employee_id) AS row_number, LEAD(annual_amount) OVER (ORDER BY annual_amount, employee_id) AS next_salary FROM "public".salaries WHERE effective_from = CAST('2025-01-01' AS DATE) ORDER BY annual_amount, employee_id LIMIT 3
```

```json
{
  "columns": [
    "employee_id",
    "annual_amount",
    "row_number",
    "next_salary"
  ],
  "rows": [
    [
      1,
      "43000.00",
      1,
      "44000.00"
    ],
    [
      2,
      "44000.00",
      2,
      "45000.00"
    ],
    [
      3,
      "45000.00",
      3,
      "46000.00"
    ]
  ]
}
```
