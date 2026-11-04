# Source ER diagram

How the 7 source files used in the core version join. `order_payments` and `geolocation` are not loaded.

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : "customer_id"
    ORDERS ||--o{ ORDER_ITEMS : "order_id"
    ORDERS ||--o{ ORDER_REVIEWS : "order_id"
    SELLERS ||--o{ ORDER_ITEMS : "seller_id"
    PRODUCTS ||--o{ ORDER_ITEMS : "product_id"
    CATEGORY_TRANSLATION ||--o{ PRODUCTS : "product_category_name"

    CUSTOMERS { string customer_id PK
                string customer_unique_id "real person"
                string customer_zip_code_prefix
                string customer_city
                string customer_state }
    ORDERS { string order_id PK
             string customer_id FK
             string order_status
             timestamp order_purchase_timestamp
             timestamp order_approved_at
             timestamp order_delivered_carrier_date
             timestamp order_delivered_customer_date
             timestamp order_estimated_delivery_date }
    ORDER_ITEMS { string order_id PK
                  int order_item_id PK
                  string product_id FK
                  string seller_id FK
                  timestamp shipping_limit_date
                  decimal price
                  decimal freight_value }
    ORDER_REVIEWS { string review_id PK
                    string order_id PK
                    int review_score
                    string review_comment_title
                    string review_comment_message
                    timestamp review_creation_date
                    timestamp review_answer_timestamp }
    SELLERS { string seller_id PK
              string seller_zip_code_prefix
              string seller_city
              string seller_state }
    PRODUCTS { string product_id PK
               string product_category_name FK
               int product_name_lenght
               int product_description_lenght
               int product_photos_qty
               int product_weight_g }
    CATEGORY_TRANSLATION { string product_category_name PK
                           string product_category_name_english }
```

Notes:
- One real customer (`customer_unique_id`) has a new `customer_id` for every order.
- One review can cover several orders, so a review row is identified by `(review_id, order_id)`.
