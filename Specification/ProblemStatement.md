# Problem Statement 

Epic:
As a user I want to track my shoppings so I am aware of my spendings 

Use case: 
- user uploads a photo of a bill 
- System sends the bill to a LLM 
- LLM returns a list of bought items with information: what was bought, how much did it cost 
- System stores data in the database 
- System displays data to the user 

# Implementation 

## Version 1. First iteration - Proof of concept 
Web application run on the local computer 
No authorization 
Database - files on the local computer 

## Version 2. Deployable version 
Web application that could be deployed on a external server 
User/password authorization 
Database - relation database 


 