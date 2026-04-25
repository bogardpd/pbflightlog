"""Functions for creating reports."""

# Standard imports
import tomllib

# Third-party imports
import pandas as pd

# Project imports
import pbflightlog.flight_log as fl

with open("config/config.toml", "rb") as f:
    CONFIG = tomllib.load(f)

def report_milestones() -> None:
    """Reports flying milestones."""

    print("Flying Distance Milestones")
    routes_df = pd.DataFrame(fl.Route.all())[
        ['origin_airport_fid', 'destination_airport_fid', 'distance_mi']
    ].set_index(['origin_airport_fid', 'destination_airport_fid'])
    flights_df = pd.DataFrame(fl.Flight.all())
    flights_df = flights_df.sort_values('departure_utc')

    # If a flight doesn't have a distance, use the route distance.
    flights_df = flights_df.join(
        routes_df,
        on=['origin_airport_fid', 'destination_airport_fid'],
        rsuffix="_route",
    )
    flights_df['distance_mi'] = flights_df['distance_mi'].fillna(
        flights_df['distance_mi_route']
    ).astype(int)

    # Find the first flight that exceeds each milestone
    flights_df['cumulative_mi'] = flights_df['distance_mi'].cumsum()
    milestone_distances_df = pd.DataFrame({
        'milestone': CONFIG['milestones']['distances']
    })
    flights_df = flights_df.reset_index(names='fid')
    total_distance = flights_df['cumulative_mi'].max()
    flights_df = pd.merge_asof(
        milestone_distances_df,
        flights_df,
        left_on='milestone',
        right_on='cumulative_mi',
        direction='forward',
    )
    flights_df = flights_df.dropna(subset=['departure_utc', 'cumulative_mi'])
    flights_df['fid'] = flights_df['fid'].astype(int)
    flights_df['cumulative_mi'] = flights_df['cumulative_mi'].astype(int)
    flights_df = flights_df.set_index('fid')

    # print(flights_df[['milestone', 'fid', 'departure_utc', 'cumulative_mi']])
    print(fl.flights_table(flights_df, extra_columns={
        'milestone': "Milestone\nMiles",
        'cumulative_mi': "Cumulative\nMiles",
    }))
    print(f"Total distance: {total_distance} mi")
