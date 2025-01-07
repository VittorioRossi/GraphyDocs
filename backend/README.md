# Goal

My goal with the backend is to create a sysetem that is able to consistently run a graph algorithm in background while continuoulsy streaming data to the forntend. This system needs to be able to handle cancellation and manage efficienttly the case when the client for some reason disconnects from the sockets but then reconnects(the algorithm was still going on when he disconnected)

# Logic
The backed has a series of modules exposing routers. The routers are importing 

## Api.py
File exposing the routers.

## Modules
- Session: 
- Mapping/Algorihtm: module with object exposing the 
- Graph: managing the interacions with Neo4j efficinetly
- Storage: file system handling

## Orchestrators
In the folder orchestrators you can find the router 