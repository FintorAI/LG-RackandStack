# LG-Blank - Windows Automation Agent Template

## Overview

**LG-Blank** is a blank LangGraph template designed for creating Windows automation agents. This template provides a foundation with pre-built action functions and a basic structure that can be easily customized to create specific automation workflows.

## What's Included

### Pre-built Action Functions
The template includes common Windows automation actions:
- **`click_action`**: Generic click functionality
- **`wait_action`**: Pause execution for specified duration
- **`input_action`**: Text input with proper formatting
- **`enter_action`**: Send ENTER key
- **`double_click_action`**: Double-click functionality
- **`screenshot_action`**: Capture screenshots with multiple format support

### State Management
- **`State`** class with common fields:
  - `user_input`: For receiving input data
  - `current_node`: Track workflow progress
  - `status`: Monitor execution status
  - `borrower_name`: Example state variable (customizable)
  - `screenshot_url`: Store captured screenshots

### Basic Structure
- LangGraph imports and setup
- WindowsAgent integration
- Error handling and logging
- Configurable OS_URL

## Getting Started

### Prerequisites
- Python 3.8+
- LangGraph
- cuteagent (Windows automation library)

### Configuration
1. Update the `OS_URL` in `src/agent/graph.py` to point to your Windows server
2. Customize the `State` class fields based on your needs
3. Create your workflow nodes using the provided action functions

### Creating Your Agent

1. **Define your workflow**: Plan out the sequence of actions your agent needs to perform
2. **Create node functions**: Use the pre-built action functions to create your workflow nodes
3. **Build the graph**: Connect your nodes using LangGraph's StateGraph
4. **Test and iterate**: Use LangGraph Studio to test and debug your workflow

### Example Usage

```python
# Create a simple workflow node
async def my_workflow_node(state: State, config: RunnableConfig) -> State:
    # Click at coordinates (100, 200)
    return await click_action(100, 200, "Click button", 1, state)

# Build your graph
graph = (
    StateGraph(State)
    .add_node("my_node", my_workflow_node)
    .add_edge("__start__", "my_node")
    .add_edge("my_node", "__end__")
    .compile(name="myCustomAgent")
)
```

### Using with JSON Configuration

This template is designed to work with JSON-based workflow configurations. You can use the `workflow_config.json` file to define your workflow structure and generate the complete agent programmatically.

## Customization

### State Fields
Modify the `State` class in `src/agent/graph.py` to include fields specific to your use case:

```python
class State(BaseModel):
    user_input: Union[str, Dict[str, Any], None] = None
    current_node: int = 0
    status: str = "Ongoing"
    # Add your custom fields here
    my_custom_field: str = "default_value"
```

### Action Functions
The template includes generic action functions that handle common Windows automation tasks. These can be used as building blocks for your specific workflow.

### Graph Structure
The template provides a minimal graph structure that you can expand based on your needs:
- Simple linear workflows
- Complex branching logic
- Subgraph organization
- Error handling and retry mechanisms

## Development

### File Structure
```
LG-blank/
├── src/agent/
│   ├── __init__.py
│   └── graph.py          # Main graph definition
├── tests/                # Test files
├── static/              # Static assets
├── workflow_config.json # JSON configuration template
└── README.md           # This file
```

### Testing
Use LangGraph Studio to test your agent:
1. Open the project folder in LangGraph Studio
2. Configure your environment variables
3. Test individual nodes and complete workflows
4. Debug and iterate on your implementation

## Best Practices

1. **Error Handling**: Each action function includes proper error handling and logging
2. **State Management**: Always update `state.current_node` and `state.status` in your nodes
3. **Modularity**: Break complex workflows into smaller, reusable nodes
4. **Documentation**: Document your custom nodes and their purpose
5. **Testing**: Test your workflows thoroughly before deployment

## Support

This template is designed to be flexible and extensible. You can:
- Add new action functions as needed
- Modify existing functions to suit your requirements
- Create complex workflows using the provided building blocks
- Integrate with external systems and APIs

## License

This template follows the same license as the parent project.