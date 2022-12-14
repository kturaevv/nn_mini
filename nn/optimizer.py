from abc import ABC, abstractmethod
from lib2to3.pgen2.token import OP
import numpy as np


class Optimizer(ABC):
    def __init__(self, decay=0., epsilon=1e-7) -> None:
        self.iterations = 0
        self.epsilon = epsilon

    def pre_update_params(self):
        if self.decay:
            self.current_learning_rate = self.learning_rate * \
                    (1. / (1. + self.decay * self.iterations))
    
    @abstractmethod
    def update_params(self):
        pass

    def post_update_params(self):
        self.iterations += 1


class SGD(Optimizer):
    def __init__(self, learning_rate=1.0, decay=0., momentum=0.):
        self.learning_rate = learning_rate
        self.current_learning_rate = learning_rate
        self.momentum = momentum
            
    def update_params(self, layer):
        if self.momentum:
            # if layer does not contain momentum arrays -> create
            if not hasattr(layer, 'weight_momentums'):
                layer.weight_momentums = np.zeros_like(layer.weights)
                layer.bias_momentums = np.zeros_like(layer.biases)
            
            weight_updates = \
                self.momentum * layer.weight_momentums - \
                self.current_learning_rate * layer.dweights
            layer.weight_momentums = weight_updates
            
            bias_updates = \
                self.momentum * layer.bias_momentums - \
                self.current_learning_rate * layer.dbiases
            layer.bias_momentums = bias_updates
            
        else: # Vanilla SGD updates
            weight_updates = - self.current_learning_rate * layer.dweights
            bias_updates = - self.current_learning_rate * layer.dbiases

        # Update weights and biases using either
        # vanilla or momentum updates
        layer.weights += weight_updates
        layer.biases += bias_updates
            

class Adagrad(Optimizer):
    
    # Optimizer Adaptive gradient, is known for adding new variable to optimization
    # which is weight and bias cache. 

    def __init__ ( self , learning_rate = 1. , decay = 0. , epsilon = 1e-7 ):
        self.learning_rate = learning_rate
        self.current_learning_rate = learning_rate

    def update_layer_cache(self, layer):
        # Update cache with squared current gradients
        layer.weight_cache += layer.dweights ** 2
        layer.bias_cache += layer.dbiases ** 2

    def update_params(self, layer):
        # If layer does not contain cache arrays,
        # create them filled with zeros
        if not hasattr (layer, 'weight_cache' ):
            layer.weight_cache = np.zeros_like(layer.weights)
            layer.bias_cache = np.zeros_like(layer.biases)
        
        self.update_layer_cache(layer)
        
        # Vanilla SGD parameter update + normalization
        layer.weights += - (
            self.current_learning_rate * layer.dweights / 
            (np.sqrt(layer.weight_cache) + self.epsilon))

        layer.biases += - (
            self.current_learning_rate * layer.dbiases / 
            (np.sqrt(layer.bias_cache) + self.epsilon))


class RMSprop(Adagrad):

    # The only difference between the classes is cache implementation.

    def __init__(self, learning_rate=0.001, decay=0., epsilon=1e-7, rho=0.9):
        self.decay = decay
        self.epsilon = epsilon

        self.learning_rate = learning_rate
        self.current_learning_rate = learning_rate
        self.rho = rho
    
    def update_layer_cache(self, layer):
        # Update cache with squared current gradients
        layer.weight_cache = self.rho * layer.weight_cache + \
        ( 1 - self.rho) * layer.dweights ** 2
        layer.bias_cache = self.rho * layer.bias_cache + \
        ( 1 - self.rho) * layer.dbiases ** 2
        

class Adam(Optimizer):
    
    def __init__(self, learning_rate=0.001, decay=0., epsilon=1e-7, beta_1=0.9, beta_2=0.999):
        self.decay = decay
        self.epsilon = epsilon

        self.learning_rate = learning_rate
        self.current_learning_rate = learning_rate

        self.beta_1 = beta_1
        self.beta_2 = beta_2

        self.iterations = 0
    
    def update_params(self, layer):
        if not hasattr(layer, 'weight_cache'):
            layer.weight_cache = np.zeros_like(layer.weights)
            layer.weight_momentums = np.zeros_like(layer.weights)
            
            layer.bias_cache = np.zeros_like(layer.biases)
            layer.bias_momentums = np.zeros_like(layer.biases)
        
        # Update momentum with current gradient
        layer.weight_momentums = self.beta_1 * layer.weight_momentums + \
            (1 - self.beta_1) * layer.dweights
        layer.bias_momentums = self.beta_1 * layer.bias_momentums + \
            (1 - self.beta_1) * layer.dbiases
        
        # Get corrected momentum ?
        weight_momentums_corrected = layer.weight_momentums / \
            (1 - self.beta_1 ** (self.iterations + 1))
        bias_momentums_corrected = layer.bias_momentums / \
            (1 - self.beta_1 ** (self.iterations + 1))
        
        # Update cache with square current gradients
        layer.weight_cache = self.beta_2 * layer.weight_cache + \
            (1 - self.beta_2) * layer.dweights ** 2
        layer.bias_cache = self.beta_2 * layer.bias_cache + \
            ( 1 - self.beta_2) * layer.dbiases ** 2
        
        # Get corrected cache?
        weight_cache_corrected = layer.weight_cache / \
            (1 - self.beta_2 ** (self.iterations + 1 ))
        bias_cache_corrected = layer.bias_cache / \
            (1 - self.beta_2 ** (self.iterations + 1 ))
        
        # Vanilla SGD + normalization with square rooted cache
        layer.weights += - self.current_learning_rate * \
            weight_momentums_corrected / (np.sqrt(weight_cache_corrected) + self.epsilon)
        layer.biases += - self.current_learning_rate * \
            bias_momentums_corrected / (np.sqrt(bias_cache_corrected) + self.epsilon)
