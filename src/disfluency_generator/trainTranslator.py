import tensorflow as tf
from encoder import Encoder
from decoder import Decoder
from shapeChecker import ShapeChecker
from decoder import DecoderInput


class TrainTranslator(tf.keras.Model):
    def __init__(self, embedding_dim, units,
                 input_text_processor,
                 output_text_processor,
                 use_tf_function=True):
        super().__init__()
        # Build the encoder and decoder
        encoder = Encoder(input_text_processor.vocabulary_size(),
                          embedding_dim, units)
        decoder = Decoder(output_text_processor.vocabulary_size(),
                          embedding_dim, units)

        self.encoder = encoder
        self.decoder = decoder
        self.input_text_processor = input_text_processor
        self.output_text_processor = output_text_processor
        self.use_tf_function = use_tf_function
        self.shape_checker = ShapeChecker()

    def train_step(self, inputs):
        self.shape_checker = ShapeChecker()
        if self.use_tf_function:
            return self._tf_train_step(inputs)
        else:
            return self._train_step(inputs)

    def _preprocess(self, input_text, target_text):
        self.shape_checker(input_text, ('batch',))
        self.shape_checker(target_text, ('batch',))

        # Convert the text to token IDs
        input_tokens = self.input_text_processor(input_text)
        target_tokens = self.output_text_processor(target_text)
        self.shape_checker(input_tokens, ('batch', 's'))
        self.shape_checker(target_tokens, ('batch', 't'))

        # Convert IDs to masks.
        input_mask = input_tokens != 0
        self.shape_checker(input_mask, ('batch', 's'))

        target_mask = target_tokens != 0
        self.shape_checker(target_mask, ('batch', 't'))

        return input_tokens, input_mask, target_tokens, target_mask

    def _train_step(self, inputs):
        input_text, target_text = inputs

        (input_tokens, input_mask, target_tokens, target_mask) = self._preprocess(input_text, target_text)

        max_target_length = tf.shape(target_tokens)[1]

        with tf.GradientTape() as tape:
            # Encode the input
            enc_output, enc_state = self.encoder(input_tokens)
            self.shape_checker(enc_output, ('batch', 's', 'enc_units'))
            self.shape_checker(enc_state, ('batch', 'enc_units'))

            # Initialize the decoder's state to the encoder's final state.
            # This only works if the encoder and decoder have the same number of
            # units.
            dec_state = enc_state
            loss = tf.constant(0.0)

            for t in tf.range(max_target_length - 1):
                # Pass in two tokens from the target sequence:
                # 1. The current input to the decoder.
                # 2. The target the target for the decoder's next prediction.
                new_tokens = target_tokens[:, t:t + 2]
                step_loss, dec_state = self._loop_step(new_tokens, input_mask,
                                                       enc_output, dec_state)
                loss = loss + step_loss

            # Average the loss over all non padding tokens.
            average_loss = loss / tf.reduce_sum(tf.cast(target_mask, tf.float32))

        # Apply an optimization step
        variables = self.trainable_variables
        gradients = tape.gradient(average_loss, variables)
        self.optimizer.apply_gradients(zip(gradients, variables))

        # Return a dict mapping metric names to current value
        return {'batch_loss': average_loss}

    def _loop_step(self, new_tokens, input_mask, enc_output, dec_state):
        input_token, target_token = new_tokens[:, 0:1], new_tokens[:, 1:2]

        # Run the decoder one step.
        decoder_input = DecoderInput(new_tokens=input_token,
                                     enc_output=enc_output,
                                     mask=input_mask)

        dec_result, dec_state = self.decoder(decoder_input, state=dec_state)
        self.shape_checker(dec_result.logits, ('batch', 't1', 'logits'))
        self.shape_checker(dec_result.attention_weights, ('batch', 't1', 's'))
        self.shape_checker(dec_state, ('batch', 'dec_units'))

        # `self.loss` returns the total for non-padded tokens
        y = target_token
        y_pred = dec_result.logits
        step_loss = self.loss(y, y_pred)

        return step_loss, dec_state

    # boosts training efficiency:
    @tf.function(input_signature=[[tf.TensorSpec(dtype=tf.string, shape=[None]),
                                   tf.TensorSpec(dtype=tf.string, shape=[None])]])
    def _tf_train_step(self, inputs):
        return self._train_step(inputs)


class BatchLogs(tf.keras.callbacks.Callback):
    def __init__(self, key):
        self.key = key
        self.logs = []

    def on_train_batch_end(self, n, logs):
        self.logs.append(logs[self.key])


if __name__ == '__main__':
    from machine_translator import create_text_processor
    from maskedLoss import MaskedLoss
    import numpy as np
    embedding_dim = 3
    units = 12
    input_samples = [
        "some sample text.",
        "another bit of sample text",
        "the story of texts",
    ]
    target_samples = [
        "some sa sample text.",
        "another another bit of sample text",
        "the story of um texts",
    ]
    input_text_processor = create_text_processor(input_samples, max_vocab_size=5)
    output_text_processor = create_text_processor(target_samples, max_vocab_size=7)
    example_input_batch = tf.constant(input_samples, )
    example_target_batch = tf.constant(target_samples, )

    translator = TrainTranslator(
        embedding_dim, units,
        input_text_processor=input_text_processor,
        output_text_processor=output_text_processor,
        use_tf_function=False)

    # Configure the loss and optimizer
    translator.compile(
        optimizer=tf.optimizers.Adam(),
        loss=MaskedLoss(),
    )

    np.log(output_text_processor.vocabulary_size())

    for n in range(10):
        print(translator.train_step([example_input_batch, example_target_batch]))

    # monitoring:
    losses = []
    for n in range(100):
      print('.', end='')
      logs = translator.train_step([example_input_batch, example_target_batch])
      losses.append(logs['batch_loss'].numpy())

    print()
    import matplotlib.pyplot as plt
    plt.plot(losses)
    plt.show()

