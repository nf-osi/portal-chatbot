# NF Portal Chatbot

Development and configuration for NF Portal-flavored Synapse chatbots.

## Description

This repository contains configuration, test datasets, and other resources for NF Portal-tailored Synapse chatbots.

## Agent Registrations

For details on all registered agents (including legacy v0 and other versions in development), see [agents/README.md](agents/README.md). 
(Note: Creating agents for Synapse is not generally available to all Synapse users. 
Nevertheless, if you came across this project and have interest and funding for Synapse agents and portals, feel free to reach out to us.)

## PHD Benchmarking and Evaluation

The Portal Help & Discovery (PHD) suite is a set of benchmarking and evaluation datasets to ensure quality standards and quantify improvements in our chatbot agents. 
Within our framework, these resources also help identify documentation gaps and inconsistencies. 
Not all datasets are stored here in this repo; references to relevant datasets will be kept up to date. 

### General Help Component

The General Help component tests the agent's ability to answer questions about NF Portal navigation, features, history, and general usage. 
The agent answers questions based on the Synapse + NF portal help docs. 

- [Test questions about NF Portal](benchmark/general-help/) -- an updated and expanded version expected soon
- Portal page navigation -- TODO

### Discovery Component

There will eventually be multiple implementations falling under the Discovery component. 
Some of the below may arguably focus more on search; the distinction sometimes depend on user phrasing. 
(Note: Search is more goal-oriented with targeted results. Discovery is for browsing, recommendations, and understanding what's available. Discovery is harder to evaluate.) 

- [Finding answers and connections with NF knowledgegraph](https://github.com/nf-osi/kg-pipeline/tree/develop/evaluation/main) 

## Contributing

We welcome contributions to improve the chatbot. To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
    ```sh
    git checkout -b feature-name
    ```
3. Commit your changes.
    ```sh
    git commit -m 'Describe your feature or fix'
    ```
4. Push to the branch.
    ```sh
    git push origin feature-name
    ```
5. Create a pull request.

## Acknowledgements

We thank the [Gilbert Family Foundation](https://gilbertfamilyfoundation.org/) for funding much of this work.

## See Also

- https://rest-docs.synapse.org/rest/index.html#org.sagebionetworks.repo.web.controller.AgentController
- [Synapse Custom Agents framework](https://sagebionetworks.jira.com/wiki/spaces/PLFM/pages/3711303683/Adding+Custom+Agents+to+Synapse) (Internal Confluence page)
- [NF design doc](https://sagebionetworks.jira.com/wiki/spaces/NPD/pages/3899359241/NF+Portal+Assistant+Agent) (Internal Confluence page) 

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
