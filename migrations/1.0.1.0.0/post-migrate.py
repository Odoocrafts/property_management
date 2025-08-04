# -*- coding: utf-8 -*-

def migrate(cr, _version):
    """Migration script to safely handle res.partner field additions"""
    
    # Check if columns exist before trying to use them
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_partner' 
        AND column_name IN ('is_property_prospect', 'is_property_customer', 'is_property_investor')
    """)
    
    existing_columns = [row[0] for row in cr.fetchall()]
    
    # Only run updates if all columns exist
    if len(existing_columns) == 3:
        # Set default values for existing partners
        cr.execute("""
            UPDATE res_partner 
            SET is_property_prospect = COALESCE(is_property_prospect, false),
                is_property_customer = COALESCE(is_property_customer, false),
                is_property_investor = COALESCE(is_property_investor, false)
            WHERE is_property_prospect IS NULL 
               OR is_property_customer IS NULL 
               OR is_property_investor IS NULL
        """)
    
    # Log completion
    print("Migration completed: res.partner property fields initialized")
