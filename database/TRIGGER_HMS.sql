-- Automatically update inventory timestamp
-- Whenever an inventory record is updated, PostgreSQL refreshes last_updated.

CREATE OR REPLACE FUNCTION update_inventory_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.last_updated := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_inventory_timestamp
BEFORE UPDATE ON inventory
FOR EACH ROW
EXECUTE FUNCTION update_inventory_timestamp();

-- Validate appointment, room, and payment statuses
-- The trigger ensures that status values match the predefined choices
CREATE OR REPLACE FUNCTION validate_status_values()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'appointments' THEN
        IF NEW.status IS NULL OR NEW.status NOT IN (
            'Scheduled',
            'Completed',
            'Cancelled',
            'No-show'
        ) THEN
            RAISE EXCEPTION
                'Invalid appointment status: %',
                NEW.status;
        END IF;

    ELSIF TG_TABLE_NAME = 'rooms' THEN
        IF NEW.status IS NULL OR NEW.status NOT IN (
            'Available',
            'Occupied',
            'Maintenance'
        ) THEN
            RAISE EXCEPTION
                'Invalid room status: %',
                NEW.status;
        END IF;

    ELSIF TG_TABLE_NAME = 'billing' THEN
        IF NEW.payment_status IS NULL
           OR NEW.payment_status NOT IN (
               'Pending',
               'Paid',
               'Partially Paid',
               'Cancelled'
           ) THEN
            RAISE EXCEPTION
                'Invalid payment status: %',
                NEW.payment_status;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_appointment_status
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

CREATE TRIGGER trg_validate_room_status
BEFORE INSERT OR UPDATE ON rooms
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

CREATE TRIGGER trg_validate_billing_status
BEFORE INSERT OR UPDATE ON billing
FOR EACH ROW
EXECUTE FUNCTION validate_status_values();

-- Prevent negative inventory quantities
-- This trigger rejects inventory records with negative quantities or negative reorder levels.
CREATE OR REPLACE FUNCTION validate_inventory()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.quantity IS NULL OR NEW.quantity < 0 THEN
        RAISE EXCEPTION
            'Inventory quantity cannot be NULL or negative';
    END IF;

    IF NEW.reorder_level IS NULL
       OR NEW.reorder_level < 0 THEN
        RAISE EXCEPTION
            'Reorder level cannot be NULL or negative';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validate_inventory
BEFORE INSERT OR UPDATE ON inventory
FOR EACH ROW
EXECUTE FUNCTION validate_inventory();