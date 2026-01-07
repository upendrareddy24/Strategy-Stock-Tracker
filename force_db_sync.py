from app import app, db, Strategy, DEFAULT_STRATEGIES

def force_sync():
    with app.app_context():
        print("Connecting to database...")
        existing = Strategy.query.all()
        default_names = [s['name'] for s in DEFAULT_STRATEGIES]
        
        print(f"Found {len(existing)} existing strategies.")
        
        # Delete old
        for x in existing:
            if x.name not in default_names:
                print(f"DELETING old strategy: {x.name}")
                db.session.delete(x)
        
        # Add/Update new
        for s in DEFAULT_STRATEGIES:
            exist = Strategy.query.filter_by(name=s['name']).first()
            if not exist:
                print(f"CREATING new strategy: {s['name']}")
                new_s = Strategy(name=s['name'], display_name=s['display_name'], tier=s['tier'], color=s['color'])
                db.session.add(new_s)
            else:
                print(f"UPDATING existing strategy: {s['name']}")
                exist.display_name = s['display_name']
                exist.tier = s['tier']
                exist.color = s['color']
        
        db.session.commit()
        print("Sync Complete!")

if __name__ == "__main__":
    force_sync()
