# Floppy
Flowchart Python -- A multipurpose Python node editor.

![Example Graph](/floppy/ressources/img.png?raw=true "Graph Example")

Floppy includes a PyQt5 based graphical editor for creating graphs consisting of logically connected nodes.
Floppy also provides an interpreter for these graphs that can run on a remote machine and is controlled via TCP/IP.

A recently added feature is the automatic concurrent execution of graphs. The Graph Interpreter will continuously check
which nodes are ready to be executed and will then create a new thread for running each node.

To execute a graph, the 'Run' button can be pressed.
This causes the editor to spawn a local graph interpreter (equivalent to pressing 'Spawn'), to push the graph to the
interpreter (equivalent to pressing 'Push') and then to unpause the interpreter (equivalent to pressing 'Unpause').


A main design goal is to make the addition of custom nodes as easy as possible. For example the following code will
make a node for adding two integer available in the editor:


    class AddIntergers(Node):
        Input('Integer1', int)
        Input('Integer2', int)
        Output('Sum', int)

    def run():
        self.o_Sum = self.i_Integer1.value + self.i_Integer2.value


While most IDEs will complain about the code the Node class's meta class takes care of making the objects 'Input' and
'Output' available in the class's scope. The meta class will also make sure the editor itself is aware of the newly
defined node class.
Every defined input can be accessed either by using 'self.i\_\<InputName\>' or by using 'self.inputs['\<InputName\>']''.
Outputs are set by assigning the new value to the  'self.o\_\<OutputName\>  property. Outputs can be accessed in general
either by 'self.o\_\<OutputName\>' or 'self.outputs['\<OutputName\>']''. The 'i_' and 'o_' prefixes thereby allow to
easily distinguiesh between inputs and outputs.
NOTE: the \_\<InputName\> and \_\<OutputName\> attribute names are deprecated, support may be removed in future versions.

By default any custom node will wait for all inputs to be set before trying to execute a node. If a more sophisticated
check is required, the 'Node.check()' method can be overridden.

After executing a node the node's 'notify()' method is called to notify all connected nodes about possible changes to
the inputs they are waiting for. Custom post-execution behavior can be implemented here.

##How To Create a Custom Node Step by Step
In order to use Floppy, a Python interpreter compatible with PyQt5 is required. This probably means Python3.4 is needed.
To use the dynamic plotting nodes, matplotlib with all its dependencies is required. However, Floppy will still work as
long as no plotting nodes are used.

Setup: Add the cloned directory to your PYTHONPATH environment variable.
Check if you can import 'floppy' in your Python3 console

 * Create a new \<FileName\>.py file in the 'CustomNodes' subdirectory. This directory is automatically scanned for 
custom nodes. Creating a new file prevents conflicts when pulling updates from Github.

 * Start the file with importing the following objects:
```python
    from floppy.node import Node, Input, Output, Tag, abstractNode
```

 * Create your custom Node. (MyNode in this case)
```python
    class MyNode(Node):
        pass
```
If the editor is started now the custom node class will be available in the list at the top-right widget.

 * Define inputs and outputs.
```python
    class MyNode(Node):
        Input('MyInput1', str)
        Input('MyInput2', float, list=True)
        Output('MyOutput1', int)
        Output('MyOutput2', bool)
```    
This will create two inputs and two outputs of the type defined by the second argument. The optional 'list' argument indicates
that a list of the appropriate type is expected. This will be visualized by a square icon instead of a circle one.
The first argument - the Input/Output name - can be any legal Python variable name and must be unique within the scope of a Node class.

 * Define the execution behavior by overriding the 'run()' method.
```python
    class MyNode(Node):
        ...
         def run(self):
            super(MyNode, self).run()
            self.i_MyInput1.value # is a reference to the accordingly named input value. The object will have the appropriate type.
            self.i_MyInput2.value # is a reference to the accordingly named input value. The object will have the appropriate type.
            self.o_MyOutput1 = 1 # will set the value of the output with the corresponding name to 1. The type must match.
            self.o_MyOutput1 = True # will set the value of the output with the corresponding name to True. The type must match.
```
Within the body of the 'run' method any legal Python3 code can be executed. Keep in mind that the method will most likely be executed
in a seperate thread. To get the most out of that feature it is recommended to use subprocesses and/or C-library calls whenever reasonable.
The call of the parent class's implementation is recommended but not necessary. This may change in the future.

 * The node should work now. Keep in mind that all outputs that are not set within the 'run' method's scope will have the value 'None'.
Several ways to further customize nodes will be discussed next but will be unnecessary for most applications.

 * Customize when a node is executed. 
```python
    class MyNode(Node):
        ...
        def check(self):
            for inp in self.inputs.values():
                if not inp.isAvailable():
                    return False
            return True
```
This is the default implementation that can be adjusted according to personal needs.
For example a time.sleep('...') can be used in combination with probing a file to continously watch a file and
analyze data streams put out by other applications.

 * Initialize custom properties.
```python
    class MyNode(Node):
        ...
        def setup(self):
            self.myCustomAttribute
```
This method is called after \__init\__ was executed. This is simply a convenient way to
avoid annoying calls of super(MyNode, self).\__init\__(*args, **kwargs).

 * Custom notification bahavior.
```python
    class MyNode(Node):
        ...
        def notify(self):
            ...
```
This method will be called after the 'run' method was executed. The method is responsible for
transferring the output values of the custom node to the inputs of the nodes connected to it.
The custom implementation looks rather confusing and will not be discussed here.
The default implementation can be checked in the base class's implementation.
An example for custom behavior that leads to branches similar to if/else constructs can be 
seen in the 'Switch' node which is also found in the floppy.node module.
Another non-standard behavior can be observed in the case of the ForEach node.

 * Custom report behavior.
```python
    class MyNode(Node):
        ...
        def report(self):
            r = super(MyNode, self).report()
            r['template'] = 'myCustomTemplate
            ...
            return r 
```
The 'report' method is called by the editor-interpreter interface whenever
a report about the nodes current status is requested by the editor. The reports
are based on HTML templates. Look at the reportWidget module and templates module
for details. However, keep in mind that the system will most likely change in the
future.

##Running the Graph Interpreter Remotely
Disclaimer: The remote graph interpreter uses exactly the same code as an interpreter spawned locally by the editor's
'Spawn' action. The only difference is that the local interpreter will accept only connections from 127.0.0.1.
This also means that the remote feature is not thoroughly tested because most of the testing was done with a locally
spawned interpreter. Theoretically, the interpreter should work remotely as well but there are cases where the latency
of a real network connection might cause unforeseen problems.

To spawn an independent remote interpreter simply run the 'RemoteInterpreter.py <portNumber>' module. The last argument
must be the port number. All other arguments are ignored.

A connection can then be established by clicking the 'Connect' button in the editor and putting in the appropriate
connection information.
