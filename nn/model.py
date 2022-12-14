import numpy as np
import pickle
import copy

from .layer import Layer_Input
from .loss import Loss, CategoricalCrossentropy

from .activation import Activation, Softmax
from .activation import Softmax_Loss_CategoricalCrossentropy

from .layer import Dense, Layer_Input

from .activation import ReLU, Softmax
from .activation import Softmax_Loss_CategoricalCrossentropy

from .accuracy import Accuracy, Categorical

from .optimizer import Adam


class Model:

    BASE, IMAGE, VIDEO, REGRESSION = 'basic', 'image', 'video', 'regression'

    def __init__(self, problem=None, structure=None):
        self.layers = []
        self.softmax_classifier_output = None
        
        viable_options = (self.BASE, self.IMAGE, self.VIDEO, self.REGRESSION)
        
        if problem and problem not in viable_options:
            print(f"{problem}, is not a viable option, try one of:")
            [print('\t- '+ i) for i in viable_options]
            return

        elif problem == self.BASE and structure:
            self.__build(problem, structure)
        
    def add(self, layer):
        self.layers.append(layer)

    def set(self, *, loss=None, optimizer=None, accuracy=None):
        if loss is not None:
            self.loss = loss
        if optimizer is not None:
            self.optimizer = optimizer
        if accuracy is not None:
            self.accuracy = accuracy
        
        self.__compile()

    def train(self, X, y, *, epochs=1, batch_size=None, print_every=1, validation_data=None, silent=False):
        # Initialize accuracy object
        self.accuracy.init(y)

        # If there is validation data passed,
        # set default number of steps for validation as well
        if validation_data is not None:
            # For better readability
            X_val, y_val = validation_data

        train_steps = self.__calculate_steps(X, batch_size)
        validation_steps = self.__calculate_steps(X_val, batch_size)

        # Main training loop
        for epoch in range(1, epochs+1):

            # Print epoch number
            print(f'epoch: {epoch}')

            # Reset accumulated values in loss and accuracy objects
            self.loss.new_pass()
            self.accuracy.new_pass()

            # Iterate over steps
            for step in range(train_steps):

                batch_X, batch_y = self.__slice_batch(X, y, step, batch_size)

                # Perform the forward pass
                output = self.forward(batch_X, training=True)

                # Calculate loss
                data_loss, regularization_loss = \
                    self.loss.calculate(output, batch_y,
                                        include_regularization=True)
                loss = data_loss + regularization_loss

                # Get predictions and calculate an accuracy
                predictions = self.output_layer.activation.predictions(output)
                accuracy = self.accuracy.calculate(predictions,batch_y)

                # Perform backward pass
                self.backward(output, batch_y)

                # Optimize (update parameters)
                self.optimizer.pre_update_params()
                for layer in self.trainable_layers:
                    self.optimizer.update_params(layer)
                self.optimizer.post_update_params()

                self._log_summary(
                    step, 
                    print_every, 
                    train_steps, 
                    accuracy, 
                    loss, 
                    data_loss, 
                    regularization_loss, 
                    type_='training')

            # Get and print epoch loss and accuracy
            epoch_data_loss, epoch_regularization_loss = \
                self.loss.calculate_accumulated(
                    include_regularization=True)
            epoch_loss = epoch_data_loss + epoch_regularization_loss
            epoch_accuracy = self.accuracy.calculate_accumulated()

            self._log_summary(
                step, 
                print_every, 
                train_steps, 
                epoch_accuracy, 
                epoch_loss, 
                epoch_data_loss, 
                epoch_regularization_loss, 
                type_='step')

        if validation_data is not None:
            self.evaluate(*validation_data, batch_size=batch_size)

    def forward(self, X, training):
        # As input layer does not have activation
        # it should be computed manually
        self.input_layer.forward(X)
        self.layers[0].forward(self.input_layer.output)

        for layer in self.layers[1:]:
            # forward propagate with previous layer activation output
            layer.forward(layer.prev.activation.output, training)
        
        # "layer" is now the last object from the list
        return layer.output

    def backward(self, output, y):
        # If combined Softmtax activation/CCE loss
        if self.softmax_classifier_output is not None:
            self.softmax_classifier_output.backward(output, y)
            # Since we'll not call backward method of the last layer
            # which is Softmax activation
            # as we used combined activation/loss
            # object, let's set dinputs in this object
            
            # self.layers[-1].dinputs = self.softmax_classifier_output.dinputs
            self.layers[-1].backward(self.softmax_classifier_output.dinputs)
            
            # Call backward method going through all the objects, 
            # except last, as it was an already combinded loss layer,
            # in reversed order passing dinputs as a parameter
            for layer in reversed(self.layers[:-1]):
                layer.backward(layer.next.dinputs)
            return

        # Calling backward on loss first will set dinput attrs for last layer
        self.loss.backward(output, y)
        self.layers[-1].backward(self.loss.dinputs)

        for layer in reversed(self.layers[:-1]):
            layer.backward(layer.next.dinputs)

    def evaluate(self, X_val, y_val, *, batch_size=None):

        validation_steps = self.__calculate_steps(X_val, batch_size)

        # Reset accumulated values in loss
        # and accuracy objects
        self.loss.new_pass()
        self.accuracy.new_pass()

        # Iterate over steps
        for step in range(validation_steps):

            batch_X, batch_y = self.__slice_batch(X_val, y_val, step, batch_size)

            # Perform the forward pass
            output = self.forward(batch_X, training=False)

            # Calculate the loss
            self.loss.calculate(output, batch_y)

            # Get predictions and calculate an accuracy
            predictions = self.output_layer.activation.predictions(
                                output)
            self.accuracy.calculate(predictions, batch_y)

        # Get and print validation loss and accuracy
        validation_loss = self.loss.calculate_accumulated()
        validation_accuracy = self.accuracy.calculate_accumulated()

        # Print a summary
        print(f'validation, ' +
                f'acc: {validation_accuracy:.3f}, ' +
                f'loss: {validation_loss:.3f}')

    def get_parameters(self):
        parameters = []

        for layer in self.trainable_layers:
            parameters.append(layer.get_parameters())

        return parameters

    def set_parameters(self, parameters):

        for parameter_set, layer in zip(parameters,
                                        self.trainable_layers):
            layer.set_parameters(*parameter_set)

    def save_parameters(self, path):

        with open(path, 'wb') as f:
            pickle.dump(self.get_parameters(), f)

    def load_parameters(self, path):

        with open(path, 'rb') as f:
            self.set_parameters(pickle.load(f))

    def save(self, path):

        model = copy.deepcopy(self)

        model.loss.new_pass()
        model.accuracy.new_pass()

        model.input_layer.__dict__.pop('output', None)
        model.loss.__dict__.pop('dinputs', None)

        for layer in model.layers:
            for property in ['inputs', 'output', 'dinputs',
                             'dweights', 'dbiases']:
                layer.__dict__.pop(property, None)

        # Open a file in the binary-write mode and save the model
        with open(path, 'wb') as f:
            pickle.dump(model, f)
    
    @staticmethod
    def load(path):
        # Open file in the binary-read mode, load a model
        with open(path, 'rb') as f:
            model = pickle.load(f)

        # Return a model
        return model
        
    def __build(self, problem, struct):
        
        def model_(hidden_layer_activation: Activation, 
                    output_layer_activation: Activation, 
                    loss: Loss, accuracy: Accuracy, optimizer):

                input_layer_index, output_layer_index = 0, len(struct) - 1

                for prev_indx, n_neurons in enumerate(struct[1:]):
                    # Typically activation vary only on output layer
                    if prev_indx == len(struct) - 2:
                        activation = output_layer_activation
                    else:
                        activation = hidden_layer_activation

                    self.add(Dense(struct[prev_indx], n_neurons, activation=activation()))

                self.set(
                    loss = loss(),
                    accuracy = accuracy(),
                    optimizer = optimizer( decay = 5e-5 ),
                )

                self.__compile()
    
        if problem == self.BASE:
            model_(
                hidden_layer_activation=ReLU,
                output_layer_activation=Softmax,
                loss=CategoricalCrossentropy,
                accuracy=Categorical,
                optimizer=Adam
            )

    def __compile(self) -> None:        
        self.input_layer = Layer_Input()

        layer_count = len(self.layers)

        self.trainable_layers = []

        # Connect layers with each other for forward and bacward pass
        for i in range(layer_count):
            if i == 0: # first layer
                self.layers[i].prev = self.input_layer
                self.layers[i].next = self.layers[i+1]
            elif i < layer_count - 1: # hidden layers
                self.layers[i].prev = self.layers[i-1]
                self.layers[i].next = self.layers[i+1]
            else: # output / last layer
                self.layers[i].prev = self.layers[i - 1 ]
                self.layers[i].next = self.loss
                self.output_layer = self.layers[i]

            # To ignore dropout-like layers
            if hasattr(self.layers[i], 'weights'):
                self.trainable_layers.append(self.layers[i]) 
        
        if self.loss is not None:
            self.loss.remember_trainable_layers(self.trainable_layers)
    
        # Softmax activation and CCE loss have combined gradient evaluation
        # which is way faster than calculating them separately
        if isinstance(self.layers[-1].activation, Softmax) and \
            isinstance (self.loss, CategoricalCrossentropy):
            self.softmax_classifier_output = \
                Softmax_Loss_CategoricalCrossentropy()
        
    def __calculate_steps(self, X, batch_size):
        
        if batch_size is not None:
            steps = len(X) // batch_size
            # Dividing rounds down. If there are some remaining
            # data but not a full batch, this won't include it
            # Add `1` to include this not full batch
            if steps * batch_size < len(X):
                steps += 1
            return steps
        else:
            # Default value if batch size is not being set
            return 1

    def __slice_batch(self, X, y, step, batch_size):
        # If batch size is not set train using one step and full dataset
        if batch_size is None:
            batch_X = X
            batch_y = y
        # Otherwise slice a batch
        else:
            from_ = step * batch_size
            to_ = (step+ 1) * batch_size

            batch_X = X[ from_ : to_ ]
            batch_y = y[ from_ : to_ ]

        return batch_X, batch_y

    def _log_summary(self, step, print_every, train_steps, accuracy, loss, data_loss, regularization_loss, type_):
        # Print a summary
        if not step % print_every or step == train_steps - 1:
            print(f'{type_}: {step}, ' +
                    f'acc: {accuracy:.3f}, ' +
                    f'loss: {loss:.3f} (' +
                    f'data_loss: {data_loss:.3f}, ' +
                    f'reg_loss: {regularization_loss:.3f}), ' +
                    f'lr: {self.optimizer.current_learning_rate}')
