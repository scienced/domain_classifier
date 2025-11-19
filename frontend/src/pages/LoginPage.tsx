/**
 * Login page component
 */
import { useState } from 'react'
import {
  Box,
  Button,
  Container,
  FormControl,
  FormLabel,
  Heading,
  Input,
  VStack,
  Text,
  useToast,
  Card,
  CardBody
} from '@chakra-ui/react'
import { apiClient } from '../services/api'

interface LoginPageProps {
  onLogin: () => void
}

export default function LoginPage({ onLogin }: LoginPageProps) {
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const toast = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      await apiClient.login(password)
      toast({
        title: 'Login successful',
        status: 'success',
        duration: 3000
      })
      onLogin()
    } catch (error) {
      toast({
        title: 'Login failed',
        description: 'Incorrect password',
        status: 'error',
        duration: 5000
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Container maxW="md" py={20}>
      <Card>
        <CardBody>
          <VStack spacing={6} align="stretch">
            <Box textAlign="center">
              <Heading size="lg" mb={2}>Brand Classification MVP</Heading>
              <Text color="gray.600">Enter password to access the tool</Text>
            </Box>

            <form onSubmit={handleSubmit}>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Password</FormLabel>
                  <Input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                  />
                </FormControl>

                <Button
                  type="submit"
                  colorScheme="blue"
                  width="100%"
                  isLoading={isLoading}
                >
                  Login
                </Button>
              </VStack>
            </form>
          </VStack>
        </CardBody>
      </Card>
    </Container>
  )
}
